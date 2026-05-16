"""
Test script service — CRUD, status transitions, versioning, and export delegation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.test_script import TestCase, TestScript, TestScriptVersion, TestStep
from app.schemas.test_script import (
    TestScriptCreate,
    TestScriptRead,
    TestScriptUpdate,
    TestScriptVersionRead,
)

log = structlog.get_logger(__name__)


class TestScriptService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── List ──────────────────────────────────────────────────────────────────

    async def list_for_system(self, system_id: UUID) -> list[TestScriptRead]:
        """Simple list — kept for backwards compat with old router."""
        result = await self._db.execute(
            select(TestScript)
            .where(TestScript.system_id == system_id, TestScript.deleted_at.is_(None))
            .options(selectinload(TestScript.cases).selectinload(TestCase.steps))
            .order_by(TestScript.created_at.desc())
        )
        return [TestScriptRead.model_validate(s) for s in result.scalars().all()]

    async def list_for_system_filtered(
        self,
        system_id: UUID,
        status_filter: str | None = None,
        export_format: str | None = None,
        business_domain: str | None = None,
        ai_generated: bool | None = None,
        requirement_id: UUID | None = None,
        search: str | None = None,
        bpo_domain: str | None = None,
    ) -> list[TestScriptRead]:
        """
        Filtered list for system.
        bpo_domain: when set, restricts results to scripts in that business_domain
                    (populated by router when caller has BPO role).
        """

        q = (
            select(TestScript)
            .where(TestScript.system_id == system_id, TestScript.deleted_at.is_(None))
            .options(selectinload(TestScript.cases).selectinload(TestCase.steps))
        )

        if status_filter:
            q = q.where(TestScript.status == status_filter)
        if export_format:
            q = q.where(TestScript.export_format == export_format)
        if ai_generated is not None:
            q = q.where(TestScript.ai_generated == ai_generated)
        if requirement_id:
            q = q.where(TestScript.requirement_id == requirement_id)

        # BPO domain restriction overrides the caller-supplied business_domain filter
        effective_domain = bpo_domain or business_domain
        if effective_domain:
            q = q.where(TestScript.business_domain == effective_domain)

        if search:
            like_term = f"%{search}%"
            q = q.where(TestScript.title.ilike(like_term))

        q = q.order_by(TestScript.created_at.desc())
        result = await self._db.execute(q)
        return [TestScriptRead.model_validate(s) for s in result.scalars().all()]

    # ── Create ────────────────────────────────────────────────────────────────

    async def create(self, system_id: UUID, body: TestScriptCreate) -> TestScriptRead:
        """Backwards-compatible create (no company_id required)."""
        script = TestScript(
            system_id=system_id,
            **body.model_dump(exclude={"cases"}),
        )
        self._db.add(script)
        await self._db.flush()
        await self._add_cases(script.id, body.cases)
        await self._db.flush()
        await self._db.refresh(script)
        return TestScriptRead.model_validate(script)

    async def create_with_context(
        self,
        system_id: UUID,
        body: TestScriptCreate,
        company_id: UUID,
        created_by: UUID,
    ) -> TestScriptRead:
        """Create with full tenant context — auto-creates initial version record."""
        script = TestScript(
            system_id=system_id,
            company_id=company_id,
            created_by=created_by,
            version=1,
            **body.model_dump(exclude={"cases"}),
        )
        self._db.add(script)
        await self._db.flush()
        await self._add_cases(script.id, body.cases)
        await self._create_version(script, change_summary="Initial version", created_by=created_by)
        await self._db.flush()
        return TestScriptRead.model_validate(script)

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get(self, script_id: UUID) -> TestScriptRead:
        script = await self._load(script_id)
        return TestScriptRead.model_validate(script)

    async def get_with_versions(self, script_id: UUID) -> TestScriptRead:
        result = await self._db.execute(
            select(TestScript)
            .where(TestScript.id == script_id, TestScript.deleted_at.is_(None))
            .options(
                selectinload(TestScript.cases).selectinload(TestCase.steps),
                selectinload(TestScript.versions),
            )
        )
        script = result.scalar_one_or_none()
        if not script:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
        return TestScriptRead.model_validate(script)

    # ── Update ────────────────────────────────────────────────────────────────

    async def update(self, script_id: UUID, body: TestScriptUpdate) -> TestScriptRead:
        """Backwards-compatible update (no versioning)."""
        script = await self._db.get(TestScript, script_id)
        if not script:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
        for field, value in body.model_dump(exclude_none=True, exclude={"change_summary"}).items():
            setattr(script, field, value)
        await self._db.flush()
        return TestScriptRead.model_validate(script)

    async def update_with_version(
        self,
        script_id: UUID,
        body: TestScriptUpdate,
        updated_by: UUID,
    ) -> TestScriptRead:
        """Update with automatic version record creation."""
        script = await self._load(script_id)

        # Snapshot current content before overwriting
        await self._create_version(
            script,
            change_summary=body.change_summary or "Content updated",
            created_by=updated_by,
        )

        for field, value in body.model_dump(exclude_none=True, exclude={"change_summary"}).items():
            setattr(script, field, value)

        script.version = (script.version or 1) + 1
        await self._db.flush()
        return TestScriptRead.model_validate(script)

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete(self, script_id: UUID) -> None:
        """Hard delete — backwards compat."""
        script = await self._db.get(TestScript, script_id)
        if not script:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
        await self._db.delete(script)
        await self._db.flush()

    async def soft_delete(self, script_id: UUID) -> None:
        """Soft delete — sets deleted_at."""
        script = await self._load(script_id)
        script.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await self._db.flush()

    # ── Status transitions ────────────────────────────────────────────────────

    async def submit_for_review(self, script_id: UUID) -> TestScriptRead:
        from app.models.enums import TestScriptStatus

        script = await self._load(script_id)
        if script.status != TestScriptStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot submit for review from status '{script.status}' — must be DRAFT",
            )
        script.status = TestScriptStatus.IN_REVIEW.value
        await self._db.flush()
        log.info("script.submitted_for_review", script_id=str(script_id))
        return TestScriptRead.model_validate(script)

    async def approve(self, script_id: UUID, approver_id: UUID) -> TestScriptRead:
        from app.models.enums import TestScriptStatus

        script = await self._load(script_id)
        if script.status not in (
            TestScriptStatus.IN_REVIEW.value,
            TestScriptStatus.DRAFT.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot approve from status '{script.status}'",
            )
        script.status = TestScriptStatus.APPROVED.value
        script.approved_by = approver_id
        script.approved_at = datetime.now(UTC).replace(tzinfo=None)
        await self._db.flush()
        log.info("script.approved", script_id=str(script_id), approver_id=str(approver_id))
        return TestScriptRead.model_validate(script)

    async def reject(
        self,
        script_id: UUID,
        rejection_comment: str,
        rejected_by: UUID,
    ) -> TestScriptRead:
        from app.models.enums import TestScriptStatus

        script = await self._load(script_id)
        if script.status not in (
            TestScriptStatus.IN_REVIEW.value,
            TestScriptStatus.APPROVED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot reject from status '{script.status}'",
            )
        script.status = TestScriptStatus.DRAFT.value
        # Store rejection reason as a version record for audit trail
        await self._create_version(
            script,
            change_summary=f"Rejected: {rejection_comment}",
            created_by=rejected_by,
        )
        await self._db.flush()
        log.info(
            "script.rejected",
            script_id=str(script_id),
            rejected_by=str(rejected_by),
        )
        return TestScriptRead.model_validate(script)

    # ── Versions ──────────────────────────────────────────────────────────────

    async def get_versions(self, script_id: UUID) -> list[TestScriptVersionRead]:
        # Ensure script exists
        await self._load(script_id)
        result = await self._db.execute(
            select(TestScriptVersion)
            .where(TestScriptVersion.test_script_id == script_id)
            .order_by(TestScriptVersion.version.desc())
        )
        return [TestScriptVersionRead.model_validate(v) for v in result.scalars().all()]

    async def get_version(self, script_id: UUID, version_number: int) -> TestScriptVersionRead:
        result = await self._db.execute(
            select(TestScriptVersion).where(
                TestScriptVersion.test_script_id == script_id,
                TestScriptVersion.version == version_number,
            )
        )
        v = result.scalar_one_or_none()
        if not v:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} not found for script {script_id}",
            )
        return TestScriptVersionRead.model_validate(v)

    # ── Export (legacy shim — delegates to ExportService) ─────────────────────

    async def export(self, script_id: UUID, fmt: str) -> tuple[bytes, str, str]:
        """Legacy export used by the old StreamingResponse router endpoint."""
        from app.exporters.base import get_exporter

        script = await self.get(script_id)
        exporter = get_exporter(fmt)
        # Minimal export without full context
        from app.exporters.base import ExportContext, ExportFormatEnum

        ctx = ExportContext(
            system_name="System",
            base_url="",
            export_format=ExportFormatEnum.PLAYWRIGHT,
        )
        content_str = exporter.export([], ctx)
        return content_str.encode(), exporter.media_type, exporter.filename(script.title)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _load(self, script_id: UUID) -> TestScript:
        result = await self._db.execute(
            select(TestScript)
            .where(TestScript.id == script_id, TestScript.deleted_at.is_(None))
            .options(selectinload(TestScript.cases).selectinload(TestCase.steps))
        )
        script = result.scalar_one_or_none()
        if not script:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
        return script

    async def _add_cases(self, script_id: UUID, cases_data: list) -> None:
        from app.schemas.test_script import TestCaseCreate

        for case_data in cases_data:
            if isinstance(case_data, TestCaseCreate):
                case_dict = case_data.model_dump(exclude={"steps"})
                steps_data = case_data.steps
            else:
                case_dict = dict(case_data)
                steps_data = case_dict.pop("steps", [])

            orm_case = TestCase(script_id=script_id, **case_dict)
            self._db.add(orm_case)
            await self._db.flush()

            for step_data in steps_data:
                if hasattr(step_data, "model_dump"):
                    step_dict = step_data.model_dump()
                else:
                    step_dict = dict(step_data)
                self._db.add(TestStep(case_id=orm_case.id, **step_dict))

    async def _create_version(
        self,
        script: TestScript,
        change_summary: str,
        created_by: UUID | None,
    ) -> TestScriptVersion:
        version = TestScriptVersion(
            test_script_id=script.id,
            version=script.version or 1,
            script_content=script.script_content,
            rendered_content=script.rendered_content,
            change_summary=change_summary,
            created_by=created_by,
        )
        self._db.add(version)
        return version
