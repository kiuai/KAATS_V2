from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_manage_content
from app.dependencies import get_db
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/systems/{system_id}/summary", dependencies=[any_authenticated])
async def project_summary(system_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    return await ReportService(db).project_summary(system_id)


@router.get("/systems/{system_id}/coverage", dependencies=[any_authenticated])
async def script_coverage(system_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    return await ReportService(db).script_coverage(system_id)


@router.get("/token_usage", dependencies=[can_manage_content])
async def token_usage(
    agent_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await ReportService(db).token_usage(
        agent_type=agent_type, date_from=date_from, date_to=date_to
    )
