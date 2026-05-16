"""
Export service — converts TestScript records to downloadable format files.
Uploads output to Blob Storage and returns time-limited SAS URLs.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exporters.base import (
    ExportContext,
    ExportFormatEnum,
    StepType,
    get_exporter,
)
from app.exporters.base import (
    TestCase as ExportTestCase,
)
from app.exporters.base import (
    TestStep as ExportTestStep,
)

log = structlog.get_logger(__name__)


@dataclass
class ExportResult:
    sas_url: str
    filename: str
    format: str
    blob_path: str


@dataclass
class BulkExportResult:
    sas_url: str
    filename: str
    script_count: int
    blob_path: str


class ExportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Public API ────────────────────────────────────────────────────────────

    async def export_script(
        self,
        script_id: UUID,
        export_format: str,
        company_id: UUID,
    ) -> ExportResult:
        """
        Export a single TestScript to the requested format.
        1. Load TestScript (verify company scope)
        2. Parse script_content JSON → list[ExportTestCase]
        3. Instantiate exporter, generate content, validate syntax
        4. Upload to Blob: exports/{company_id}/{system_id}/{script_id}/{format}.{ext}
        5. Return SAS URL (1-hour expiry) + filename + format
        """
        from app.blob import generate_sas_url, upload_bytes
        from app.models.system import System

        script = await self._load_script(script_id)
        self._check_company_scope(script, company_id)

        # Resolve system context
        system_name = "System Under Test"
        base_url = ""
        sys_obj = await self._db.get(System, script.system_id)
        if sys_obj:
            system_name = sys_obj.name
            base_url = sys_obj.base_url or ""

        fmt_enum = self._resolve_format_enum(export_format)
        ctx = ExportContext(system_name=system_name, base_url=base_url, export_format=fmt_enum)

        test_cases = self._parse_script_content(script)
        exporter = get_exporter(export_format)
        content_str = exporter.export(test_cases, ctx)

        is_valid, errors = exporter.validate(content_str)
        if not is_valid:
            log.warning(
                "export.validation_warnings",
                script_id=str(script_id),
                format=export_format,
                errors=errors,
            )

        content_bytes = content_str.encode("utf-8")
        filename = exporter.filename(script.title)
        blob_path = (
            f"exports/{company_id}/{script.system_id}/{script_id}/{export_format}/{filename}"
        )

        await upload_bytes(blob_path, content_bytes, exporter.media_type)
        sas_url = generate_sas_url(blob_path, ttl_hours=1)

        log.info(
            "export.script_exported",
            script_id=str(script_id),
            format=export_format,
            blob_path=blob_path,
        )
        return ExportResult(
            sas_url=sas_url,
            filename=filename,
            format=export_format,
            blob_path=blob_path,
        )

    async def export_bulk(
        self,
        script_ids: list[UUID],
        export_format: str,
        company_id: UUID,
    ) -> BulkExportResult:
        """
        Export multiple scripts, zip all files, return ZIP SAS URL.
        Scripts that fail individually are skipped with a warning.
        """
        from app.blob import generate_sas_url, upload_bytes
        from app.models.system import System

        zip_buffer = io.BytesIO()
        count = 0

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for script_id in script_ids:
                try:
                    script = await self._load_script(script_id)
                    self._check_company_scope(script, company_id)

                    sys_obj = await self._db.get(System, script.system_id)
                    fmt_enum = self._resolve_format_enum(export_format)
                    ctx = ExportContext(
                        system_name=sys_obj.name if sys_obj else "System",
                        base_url=(sys_obj.base_url or "") if sys_obj else "",
                        export_format=fmt_enum,
                    )

                    test_cases = self._parse_script_content(script)
                    exporter = get_exporter(export_format)
                    content_str = exporter.export(test_cases, ctx)
                    zf.writestr(exporter.filename(script.title), content_str)
                    count += 1
                except HTTPException:
                    raise
                except Exception as exc:
                    log.warning(
                        "export.bulk_script_skipped",
                        script_id=str(script_id),
                        error=str(exc),
                    )

        if count == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No scripts could be exported",
            )

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        zip_filename = f"bulk_export_{export_format}_{timestamp}.zip"
        blob_path = f"exports/{company_id}/bulk/{timestamp}/{zip_filename}"

        await upload_bytes(blob_path, zip_buffer.getvalue(), "application/zip")
        sas_url = generate_sas_url(blob_path, ttl_hours=1)

        log.info("export.bulk_complete", count=count, format=export_format)
        return BulkExportResult(
            sas_url=sas_url,
            filename=zip_filename,
            script_count=count,
            blob_path=blob_path,
        )

    async def export_cycle(
        self,
        cycle_id: UUID,
        export_format: str,
        company_id: UUID,
    ) -> BulkExportResult:
        """Export all APPROVED scripts in a test cycle as a ZIP."""
        from app.models.enums import TestScriptStatus
        from app.models.test_cycle import TestAssignment
        from app.models.test_script import TestScript

        result = await self._db.execute(
            select(TestAssignment).where(TestAssignment.test_cycle_id == cycle_id)
        )
        assignments = result.scalars().all()

        script_ids: list[UUID] = []
        for assignment in assignments:
            script_result = await self._db.execute(
                select(TestScript.id).where(
                    TestScript.id == assignment.test_script_id,
                    TestScript.status == TestScriptStatus.APPROVED.value,
                    TestScript.deleted_at.is_(None),
                )
            )
            sid = script_result.scalar_one_or_none()
            if sid is not None:
                script_ids.append(sid)

        if not script_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No approved scripts found in this cycle",
            )

        return await self.export_bulk(script_ids, export_format, company_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _load_script(self, script_id: UUID):
        from app.models.test_script import TestCase, TestScript

        result = await self._db.execute(
            select(TestScript)
            .where(TestScript.id == script_id, TestScript.deleted_at.is_(None))
            .options(selectinload(TestScript.cases).selectinload(TestCase.steps))
        )
        script = result.scalar_one_or_none()
        if script is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TestScript {script_id} not found",
            )
        return script

    def _check_company_scope(self, script, company_id: UUID) -> None:
        if script.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this test script",
            )

    @staticmethod
    def _resolve_format_enum(fmt: str) -> ExportFormatEnum:
        try:
            return ExportFormatEnum(fmt)
        except ValueError:
            return ExportFormatEnum.PLAYWRIGHT

    def _parse_script_content(self, script) -> list[ExportTestCase]:
        """
        Parse script_content JSON → list[ExportTestCase].
        Falls back to ORM cases/steps if content is absent or unparseable.
        """
        if script.script_content:
            try:
                data = json.loads(script.script_content)
                cases_raw = data.get("test_cases", data) if isinstance(data, dict) else data
                if isinstance(cases_raw, list) and cases_raw:
                    return [self._parse_case(c) for c in cases_raw]
            except Exception as exc:
                log.warning(
                    "export.parse_script_content_failed",
                    script_id=str(script.id),
                    error=str(exc),
                )

        return self._cases_from_orm(script)

    def _parse_case(self, raw: dict) -> ExportTestCase:
        steps = [self._parse_step(i + 1, s) for i, s in enumerate(raw.get("steps", []))]
        return ExportTestCase(
            id=str(raw.get("id", "")),
            title=raw.get("title", raw.get("name", "Test Case")),
            description=raw.get("description", ""),
            preconditions=raw.get("preconditions", []),
            steps=steps,
            expected_outcome=raw.get("expected_outcome", ""),
            test_type=raw.get("test_type", "positive"),
            priority=raw.get("priority", "medium"),
        )

    @staticmethod
    def _parse_step(default_number: int, raw: dict) -> ExportTestStep:
        step_type_str = raw.get("step_type", raw.get("type", "")).upper()
        try:
            step_type = StepType[step_type_str]
        except KeyError:
            action_lower = raw.get("action", "").lower()
            if any(k in action_lower for k in ("navigate", "go to", "open", "visit")):
                step_type = StepType.NAVIGATE
            elif any(k in action_lower for k in ("click", "press", "submit", "tap")):
                step_type = StepType.CLICK
            elif any(k in action_lower for k in ("enter", "type", "fill", "input")):
                step_type = StepType.INPUT
            elif any(k in action_lower for k in ("select", "choose", "pick")):
                step_type = StepType.SELECT
            elif any(k in action_lower for k in ("assert", "verify", "check", "confirm")):
                step_type = StepType.ASSERT
            elif "wait" in action_lower:
                step_type = StepType.WAIT
            elif "screenshot" in action_lower:
                step_type = StepType.SCREENSHOT
            else:
                step_type = StepType.CLICK

        return ExportTestStep(
            number=raw.get("number", raw.get("step_number", default_number)),
            action=raw.get("action", ""),
            locator_hint=raw.get("locator_hint", raw.get("locator", raw.get("selector", ""))),
            input_value=raw.get("input_value", raw.get("value", raw.get("data", ""))),
            expected_result=raw.get("expected_result", raw.get("expected_outcome", "")),
            step_type=step_type,
        )

    @staticmethod
    def _infer_step_type(action: str) -> StepType:
        a = action.lower()
        if any(k in a for k in ("navigate", "go to", "open", "visit")):
            return StepType.NAVIGATE
        if any(k in a for k in ("click", "press", "submit", "tap")):
            return StepType.CLICK
        if any(k in a for k in ("enter", "type", "fill", "input")):
            return StepType.INPUT
        if any(k in a for k in ("select", "choose", "pick")):
            return StepType.SELECT
        if any(k in a for k in ("assert", "verify", "check", "confirm")):
            return StepType.ASSERT
        if "wait" in a:
            return StepType.WAIT
        if "screenshot" in a:
            return StepType.SCREENSHOT
        return StepType.CLICK

    def _cases_from_orm(self, script) -> list[ExportTestCase]:
        """Build ExportTestCase list from ORM TestCase/TestStep relationships."""
        cases: list[ExportTestCase] = []
        for orm_case in getattr(script, "cases", []):
            steps: list[ExportTestStep] = []
            for orm_step in getattr(orm_case, "steps", []):
                params = orm_step.parameters or {}
                steps.append(
                    ExportTestStep(
                        number=orm_step.step_number,
                        action=orm_step.action,
                        locator_hint=params.get("locator", params.get("selector", "")),
                        input_value=params.get("value", params.get("input", "")),
                        expected_result=orm_step.expected_outcome or "",
                        step_type=self._infer_step_type(orm_step.action),
                    )
                )
            cases.append(
                ExportTestCase(
                    id=str(orm_case.id),
                    title=orm_case.name,
                    description=orm_case.description or "",
                    preconditions=[],
                    steps=steps,
                    expected_outcome="",
                    test_type="positive",
                    priority="medium",
                )
            )
        return cases
