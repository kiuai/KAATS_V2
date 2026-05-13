from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.blob import download_bytes, generate_sas_url, build_evidence_path
from app.models.execution_evidence import ExecutionRun, ExecutionStepResult
from app.models.test_result import EvidenceScreenshot
from app.schemas.evidence import (
    EvidenceScreenshotRead,
    EvidenceVerifyResult,
    ExecutionRunRead,
    ExecutionStepResultRead,
)


class EvidenceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── ExecutionRun queries ──────────────────────────────────────────────────

    async def list_execution_runs(self, system_id: UUID) -> list[ExecutionRunRead]:
        """List ExecutionRuns for a system (via TestScript.system_id)."""
        from app.models.test_script import TestScript

        result = await self._db.execute(
            select(ExecutionRun)
            .join(TestScript, ExecutionRun.test_script_id == TestScript.id)
            .where(TestScript.system_id == system_id)
            .order_by(ExecutionRun.created_at.desc())
        )
        runs = result.scalars().all()
        return [ExecutionRunRead.model_validate(r) for r in runs]

    async def get_execution_run(self, run_id: UUID) -> ExecutionRunRead:
        """Return full ExecutionRun with all step results loaded."""
        result = await self._db.execute(
            select(ExecutionRun)
            .where(ExecutionRun.id == run_id)
            .options(selectinload(ExecutionRun.step_results))
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution run not found",
            )
        validated = ExecutionRunRead.model_validate(run)
        validated.step_results = [
            ExecutionStepResultRead.model_validate(s)
            for s in sorted(run.step_results, key=lambda s: s.step_number)
        ]
        return validated

    async def get_report_sas_url(self, run_id: UUID) -> str:
        """Return a 1-hour SAS URL for the evidence PDF of an ExecutionRun."""
        run = await self._db.get(ExecutionRun, run_id)
        if run is None or not run.evidence_pdf_blob_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence report not found",
            )
        # Extract blob path from stored URL
        pdf_url = run.evidence_pdf_blob_url
        if "/kaats-evidence/" in pdf_url:
            blob_path = pdf_url.split("/kaats-evidence/", 1)[1].split("?")[0]
        else:
            blob_path = pdf_url
        return generate_sas_url(blob_path, ttl_hours=1)

    async def get_step_screenshot_sas_url(
        self, run_id: UUID, step_number: int
    ) -> str:
        """Return a 1-hour SAS URL for a specific step's screenshot."""
        result = await self._db.execute(
            select(ExecutionStepResult)
            .where(
                ExecutionStepResult.execution_run_id == run_id,
                ExecutionStepResult.step_number == step_number,
            )
        )
        step = result.scalar_one_or_none()
        if step is None or not step.screenshot_blob_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Screenshot for step {step_number} not found",
            )
        url = step.screenshot_blob_url
        if "/kaats-evidence/" in url:
            blob_path = url.split("/kaats-evidence/", 1)[1].split("?")[0]
        else:
            blob_path = url
        return generate_sas_url(blob_path, ttl_hours=1)

    # ── Legacy EvidenceScreenshot queries ─────────────────────────────────────

    async def list_screenshots(self, execution_id: UUID) -> list[EvidenceScreenshotRead]:
        result = await self._db.execute(
            select(EvidenceScreenshot)
            .where(
                EvidenceScreenshot.execution_id == execution_id,
                EvidenceScreenshot.deleted_at.is_(None),
            )
            .order_by(EvidenceScreenshot.step_number)
        )
        return [EvidenceScreenshotRead.model_validate(s) for s in result.scalars().all()]

    async def get_screenshot_with_sas(self, screenshot_id: UUID) -> EvidenceScreenshotRead:
        s = await self._db.get(EvidenceScreenshot, screenshot_id)
        if not s or s.deleted_at:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screenshot not found",
            )
        return EvidenceScreenshotRead.model_validate(s)

    async def verify_integrity(self, execution_id: UUID) -> EvidenceVerifyResult:
        result = await self._db.execute(
            select(EvidenceScreenshot)
            .where(
                EvidenceScreenshot.execution_id == execution_id,
                EvidenceScreenshot.deleted_at.is_(None),
            )
            .order_by(EvidenceScreenshot.step_number)
        )
        screenshots = result.scalars().all()
        failed_steps: list[int] = []
        for s in screenshots:
            try:
                data = await download_bytes(s.blob_path)
                if hashlib.sha256(data).hexdigest() != s.sha256:
                    failed_steps.append(s.step_number)
            except Exception:
                failed_steps.append(s.step_number)
        return EvidenceVerifyResult(
            valid=len(failed_steps) == 0,
            failed_steps=failed_steps,
            checked_at=datetime.now(timezone.utc),
        )

    async def delete_evidence(self, execution_id: UUID) -> None:
        result = await self._db.execute(
            select(EvidenceScreenshot).where(
                EvidenceScreenshot.execution_id == execution_id,
                EvidenceScreenshot.deleted_at.is_(None),
            )
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for s in result.scalars().all():
            s.deleted_at = now
        await self._db.flush()
