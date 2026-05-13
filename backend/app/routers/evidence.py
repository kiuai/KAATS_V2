from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_manage_content
from app.dependencies import get_db
from app.schemas.evidence import EvidenceScreenshotRead, EvidenceVerifyResult
from app.services.evidence_service import EvidenceService

router = APIRouter(tags=["evidence"])


@router.get("/executions/{execution_id}/evidence", response_model=list[EvidenceScreenshotRead], dependencies=[any_authenticated])
async def list_screenshots(
    execution_id: UUID, db: AsyncSession = Depends(get_db)
) -> list[EvidenceScreenshotRead]:
    return await EvidenceService(db).list_screenshots(execution_id)


@router.get("/evidence/{screenshot_id}", response_model=EvidenceScreenshotRead, dependencies=[any_authenticated])
async def get_screenshot(
    screenshot_id: UUID, db: AsyncSession = Depends(get_db)
) -> EvidenceScreenshotRead:
    return await EvidenceService(db).get_screenshot_with_sas(screenshot_id)


@router.get("/executions/{execution_id}/evidence/report", dependencies=[any_authenticated])
async def download_report(
    execution_id: UUID, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    sas_url = await EvidenceService(db).get_report_sas_url(execution_id)
    return RedirectResponse(url=sas_url, status_code=302)


@router.post("/executions/{execution_id}/evidence/verify", response_model=EvidenceVerifyResult, dependencies=[any_authenticated])
async def verify_integrity(
    execution_id: UUID, db: AsyncSession = Depends(get_db)
) -> EvidenceVerifyResult:
    return await EvidenceService(db).verify_integrity(execution_id)


@router.delete("/executions/{execution_id}/evidence", status_code=204, response_model=None, dependencies=[can_manage_content])
async def delete_evidence(execution_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await EvidenceService(db).delete_evidence(execution_id)
