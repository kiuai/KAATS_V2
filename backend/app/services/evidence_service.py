from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.blob import download_bytes, generate_sas_url
from app.models.test_result import EvidenceScreenshot
from app.schemas.evidence import EvidenceScreenshotRead, EvidenceVerifyResult


class EvidenceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_screenshots(self, execution_id: UUID) -> list[EvidenceScreenshotRead]:
        result = await self._db.execute(
            select(EvidenceScreenshot)
            .where(
                EvidenceScreenshot.execution_id == execution_id,
                EvidenceScreenshot.deleted_at.is_(None),
            )
            .order_by(EvidenceScreenshot.step_number)
        )
        screenshots = result.scalars().all()
        return [
            EvidenceScreenshotRead(
                **{k: v for k, v in s.__dict__.items() if not k.startswith("_")},
                sas_url=generate_sas_url(s.blob_path),
            )
            for s in screenshots
        ]

    async def get_screenshot_with_sas(self, screenshot_id: UUID) -> EvidenceScreenshotRead:
        s = await self._db.get(EvidenceScreenshot, screenshot_id)
        if not s or s.deleted_at:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screenshot not found")
        return EvidenceScreenshotRead(
            **{k: v for k, v in s.__dict__.items() if not k.startswith("_")},
            sas_url=generate_sas_url(s.blob_path),
        )

    async def get_report_sas_url(self, execution_id: UUID) -> str:
        from app.models.agent_run import AgentRun
        result = await self._db.execute(
            select(AgentRun).where(AgentRun.execution_id == execution_id)
        )
        run = result.scalar_one_or_none()
        if not run or not run.evidence_pdf_path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence report not found")
        return generate_sas_url(run.evidence_pdf_path)

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
                actual_hash = hashlib.sha256(data).hexdigest()
                if actual_hash != s.sha256:
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
