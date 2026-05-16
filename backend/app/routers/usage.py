"""Usage & quota router.

GET  /api/v1/usage/quota    — current month quota status (any authenticated)
GET  /api/v1/usage/history  — monthly history, last N months (any authenticated)
GET  /api/v1/usage/plan     — company plan details (company_admin+)
PATCH /api/v1/usage/plan    — update plan tier / limits (global_admin only)
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import any_authenticated, can_manage_company, platform_admin_only
from app.dependencies import get_current_company_id, get_db
from app.services.usage_service import UsageService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/usage", tags=["usage"])


# ── Response schemas ──────────────────────────────────────────────────────────


class QuotaStatusRead(BaseModel):
    plan_tier: str
    tokens_used: int
    tokens_limit: int | None
    tokens_pct: float | None
    tokens_warning: bool
    tokens_exceeded: bool
    runs_used: int
    runs_limit: int | None
    runs_pct: float | None
    runs_warning: bool
    runs_exceeded: bool
    max_systems: int | None
    max_users: int | None
    max_concurrent_agents: int | None
    estimated_cost_usd: Decimal


class MonthlyUsageRead(BaseModel):
    year: int
    month: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    agent_runs: int
    estimated_cost_usd: Decimal


class PlanRead(BaseModel):
    id: UUID
    company_id: UUID
    plan_tier: str
    monthly_token_limit: int | None
    monthly_agent_run_limit: int | None
    max_systems: int | None
    max_users: int | None
    max_concurrent_agents: int | None
    override_reason: str | None

    model_config = {"from_attributes": True}


class PlanPatch(BaseModel):
    plan_tier: str
    monthly_token_limit: int | None = None
    monthly_agent_run_limit: int | None = None
    max_systems: int | None = None
    max_users: int | None = None
    max_concurrent_agents: int | None = None
    override_reason: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/quota",
    response_model=QuotaStatusRead,
    dependencies=[any_authenticated],
    summary="Current month quota status",
)
async def get_quota(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> QuotaStatusRead:
    company_id = get_current_company_id(request)
    qs = await UsageService(db).get_quota_status(company_id)
    return QuotaStatusRead(
        plan_tier=qs.plan_tier,
        tokens_used=qs.tokens_used,
        tokens_limit=qs.tokens_limit,
        tokens_pct=qs.tokens_pct,
        tokens_warning=qs.tokens_warning,
        tokens_exceeded=qs.tokens_exceeded,
        runs_used=qs.runs_used,
        runs_limit=qs.runs_limit,
        runs_pct=qs.runs_pct,
        runs_warning=qs.runs_warning,
        runs_exceeded=qs.runs_exceeded,
        max_systems=qs.max_systems,
        max_users=qs.max_users,
        max_concurrent_agents=qs.max_concurrent_agents,
        estimated_cost_usd=qs.estimated_cost_usd,
    )


@router.get(
    "/history",
    response_model=list[MonthlyUsageRead],
    dependencies=[any_authenticated],
    summary="Monthly usage history",
)
async def get_usage_history(
    request: Request,
    months: int = 6,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[MonthlyUsageRead]:
    company_id = get_current_company_id(request)
    rows = await UsageService(db).get_usage_history(company_id, months=min(months, 24))
    return [
        MonthlyUsageRead(
            year=r.year,
            month=r.month,
            total_tokens=r.total_tokens,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            agent_runs=r.agent_runs,
            estimated_cost_usd=r.estimated_cost_usd,
        )
        for r in rows
    ]


@router.get(
    "/plan",
    response_model=PlanRead | None,
    dependencies=[can_manage_company],
    summary="Company plan details",
)
async def get_plan(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> PlanRead | None:
    company_id = get_current_company_id(request)
    plan = await UsageService(db).get_plan(company_id)
    if plan is None:
        return None
    return PlanRead.model_validate(plan)


@router.patch(
    "/plan",
    response_model=PlanRead,
    dependencies=[platform_admin_only],
    summary="Update company plan (platform admin only)",
)
async def update_plan(
    body: PlanPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> PlanRead:
    company_id = get_current_company_id(request)
    plan = await UsageService(db).upsert_plan(
        company_id=company_id,
        plan_tier=body.plan_tier,
        monthly_token_limit=body.monthly_token_limit,
        monthly_agent_run_limit=body.monthly_agent_run_limit,
        max_systems=body.max_systems,
        max_users=body.max_users,
        max_concurrent_agents=body.max_concurrent_agents,
        override_reason=body.override_reason,
    )
    await db.commit()
    return PlanRead.model_validate(plan)
