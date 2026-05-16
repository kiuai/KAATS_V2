"""Reports router — 5 report endpoints with Permission guards."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import (
    Permission,
    any_authenticated,
    can_manage_company,
    can_manage_content,
    require_system_access,
)
from app.dependencies import get_db
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


# ── Legacy endpoints (backwards compat) ───────────────────────────────────────


@router.get(
    "/systems/{system_id}/summary", dependencies=[any_authenticated], include_in_schema=False
)
async def project_summary(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await ReportService(db).project_summary(system_id)


@router.get(
    "/systems/{system_id}/coverage", dependencies=[any_authenticated], include_in_schema=False
)
async def script_coverage(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await ReportService(db).script_coverage(system_id)


@router.get("/token_usage", dependencies=[can_manage_content], include_in_schema=False)
async def token_usage_legacy(
    agent_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await ReportService(db).token_usage(
        agent_type=agent_type, date_from=date_from, date_to=date_to
    )


# ── New endpoints ─────────────────────────────────────────────────────────────


@router.get("/systems/{system_id}/coverage-by-domain")
async def coverage_by_domain(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.REPORT_READ),
) -> dict:
    """Requirement and test script coverage broken down by business domain."""
    return await ReportService(db).coverage_by_domain(system_id)


@router.get("/systems/{system_id}/execution-history")
async def execution_history(
    system_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.REPORT_READ),
) -> dict:
    """Recent AgentRun execution history for a system."""
    return await ReportService(db).execution_history(
        system_id=system_id,
        limit=limit,
        days=days,
    )


@router.get("/test-cycles/{cycle_id}/summary")
async def cycle_summary(
    cycle_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Pass/fail/blocked/skipped counts and pass rate for a test cycle."""
    return await ReportService(db).cycle_summary(cycle_id)


@router.get("/companies/{company_id}/overview")
async def company_overview(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = can_manage_company,
) -> dict:
    """High-level stats across the entire company."""
    return await ReportService(db).company_overview(company_id)


@router.get("/companies/{company_id}/ai-usage")
async def ai_usage(
    company_id: UUID,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    agent_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object = can_manage_company,
) -> dict:
    """AI token usage for a company with optional filters."""
    return await ReportService(db).ai_usage(
        company_id=company_id,
        date_from=date_from,
        date_to=date_to,
        agent_type=agent_type,
    )
