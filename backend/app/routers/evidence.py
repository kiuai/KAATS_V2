from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import (
    Permission,
    any_authenticated,
    can_manage_content,
    require_system_access,
)
from app.dependencies import get_db
from app.schemas.evidence import (
    EvidenceScreenshotRead,
    EvidenceVerifyResult,
    ExecutionRunRead,
)
from app.services.evidence_service import EvidenceService

router = APIRouter(tags=["evidence"])


# ── Execution runs ────────────────────────────────────────────────────────────


@router.get(
    "/systems/{system_id}/execution-runs",
    response_model=list[ExecutionRunRead],
    dependencies=[require_system_access(Permission.EVIDENCE_READ)],
)
async def list_execution_runs(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ExecutionRunRead]:
    """List all execution runs for a system, with outcome summary."""
    return await EvidenceService(db).list_execution_runs(system_id)


@router.get(
    "/execution-runs/{run_id}",
    response_model=ExecutionRunRead,
    dependencies=[any_authenticated],
)
async def get_execution_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ExecutionRunRead:
    """Return full execution run detail including all step results."""
    return await EvidenceService(db).get_execution_run(run_id)


@router.get(
    "/execution-runs/{run_id}/report",
    dependencies=[any_authenticated],
)
async def download_evidence_report(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Redirect to a time-limited SAS URL for the evidence PDF (1-hour expiry)."""
    sas_url = await EvidenceService(db).get_report_sas_url(run_id)
    return RedirectResponse(url=sas_url, status_code=302)


@router.get(
    "/execution-runs/{run_id}/steps/{step_number}/screenshot",
    dependencies=[any_authenticated],
)
async def get_step_screenshot(
    run_id: UUID,
    step_number: int,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Redirect to a time-limited SAS URL for an individual step screenshot."""
    sas_url = await EvidenceService(db).get_step_screenshot_sas_url(run_id, step_number)
    return RedirectResponse(url=sas_url, status_code=302)


# ── Legacy evidence screenshot routes (kept for backwards compatibility) ──────


@router.get(
    "/executions/{execution_id}/evidence",
    response_model=list[EvidenceScreenshotRead],
    dependencies=[any_authenticated],
)
async def list_screenshots(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceScreenshotRead]:
    return await EvidenceService(db).list_screenshots(execution_id)


@router.get(
    "/evidence/{screenshot_id}",
    response_model=EvidenceScreenshotRead,
    dependencies=[any_authenticated],
)
async def get_screenshot(
    screenshot_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EvidenceScreenshotRead:
    return await EvidenceService(db).get_screenshot_with_sas(screenshot_id)


@router.get(
    "/executions/{execution_id}/evidence/report",
    dependencies=[any_authenticated],
)
async def download_report_legacy(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    sas_url = await EvidenceService(db).get_report_sas_url(execution_id)
    return RedirectResponse(url=sas_url, status_code=302)


@router.post(
    "/executions/{execution_id}/evidence/verify",
    response_model=EvidenceVerifyResult,
    dependencies=[any_authenticated],
)
async def verify_integrity(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EvidenceVerifyResult:
    return await EvidenceService(db).verify_integrity(execution_id)


@router.delete(
    "/executions/{execution_id}/evidence",
    status_code=204,
    response_model=None,
    dependencies=[can_manage_content],
)
async def delete_evidence(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await EvidenceService(db).delete_evidence(execution_id)
