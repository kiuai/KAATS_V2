"""Platform-admin dashboard endpoints (GLOBAL_ADMIN only).

GET  /admin/overview                    — platform-wide aggregate stats
GET  /admin/companies                   — all companies with usage stats
GET  /admin/companies/{company_id}      — single company with history
PATCH /admin/companies/{company_id}/plan — update a company plan tier
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import platform_admin_only
from app.dependencies import get_db
from app.models.agent_run import AgentRun, CompanyTokenUsage
from app.models.plan import CompanyPlan
from app.models.role import UserRole
from app.models.system import System
from app.models.tenant import Company, Enterprise
from app.services.audit_service import AuditService
from app.services.usage_service import UsageService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["platform-admin"])


# ── Response schemas ──────────────────────────────────────────────────────────


class PlatformOverview(BaseModel):
    total_enterprises: int
    active_enterprises: int
    total_companies: int
    active_companies: int
    total_users: int
    agent_runs_this_month: int
    tokens_this_month: int
    estimated_cost_usd: Decimal


class CompanyAdminRead(BaseModel):
    id: UUID
    name: str
    slug: str
    enterprise_id: UUID
    enterprise_name: str
    is_active: bool
    plan_tier: str
    user_count: int
    system_count: int
    tokens_this_month: int
    runs_this_month: int
    created_at: datetime


class MonthlyUsageSummary(BaseModel):
    year: int
    month: int
    total_tokens: int
    agent_runs: int
    estimated_cost_usd: Decimal


class CompanyAdminDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    enterprise_id: UUID
    enterprise_name: str
    industry: str | None
    is_active: bool
    plan_tier: str
    monthly_token_limit: int | None
    monthly_run_limit: int | None
    user_count: int
    system_count: int
    tokens_this_month: int
    runs_this_month: int
    created_at: datetime
    usage_history: list[MonthlyUsageSummary]


class PlanPatchBody(BaseModel):
    plan_tier: str
    monthly_token_limit: int | None = None
    monthly_agent_run_limit: int | None = None
    max_systems: int | None = None
    max_users: int | None = None
    max_concurrent_agents: int | None = None
    override_reason: str | None = None


class PlanResponse(BaseModel):
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


# ── Helpers ───────────────────────────────────────────────────────────────────


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def _company_stats_stmt(ms: datetime):  # type: ignore[return]
    """Build the compound SELECT for company list stats (shared by list + detail)."""
    user_sq = (
        select(
            UserRole.company_id,
            func.count(distinct(UserRole.user_id)).label("user_count"),
        )
        .where(UserRole.company_id.isnot(None))
        .group_by(UserRole.company_id)
        .subquery()
    )
    system_sq = (
        select(
            System.company_id,
            func.count(System.id).label("system_count"),
        )
        .where(System.is_deleted == False)  # noqa: E712
        .group_by(System.company_id)
        .subquery()
    )
    plan_sq = select(CompanyPlan.company_id, CompanyPlan.plan_tier).subquery()
    token_sq = (
        select(
            CompanyTokenUsage.company_id,
            func.sum(CompanyTokenUsage.prompt_tokens + CompanyTokenUsage.completion_tokens).label(
                "tokens_this_month"
            ),
            func.sum(CompanyTokenUsage.total_cost_usd).label("cost_this_month"),
        )
        .where(CompanyTokenUsage.usage_date >= ms)
        .group_by(CompanyTokenUsage.company_id)
        .subquery()
    )
    run_sq = (
        select(
            AgentRun.company_id,
            func.count(AgentRun.id).label("runs_this_month"),
        )
        .where(AgentRun.created_at >= ms)
        .group_by(AgentRun.company_id)
        .subquery()
    )
    return (
        select(
            Company.id,
            Company.name,
            Company.slug,
            Company.enterprise_id,
            Company.is_active,
            Company.industry,
            Company.created_at,
            Enterprise.name.label("enterprise_name"),
            func.coalesce(user_sq.c.user_count, 0).label("user_count"),
            func.coalesce(system_sq.c.system_count, 0).label("system_count"),
            func.coalesce(plan_sq.c.plan_tier, "free").label("plan_tier"),
            func.coalesce(token_sq.c.tokens_this_month, 0).label("tokens_this_month"),
            func.coalesce(token_sq.c.cost_this_month, 0).label("cost_this_month"),
            func.coalesce(run_sq.c.runs_this_month, 0).label("runs_this_month"),
        )
        .join(Enterprise, Company.enterprise_id == Enterprise.id)
        .outerjoin(user_sq, Company.id == user_sq.c.company_id)
        .outerjoin(system_sq, Company.id == system_sq.c.company_id)
        .outerjoin(plan_sq, Company.id == plan_sq.c.company_id)
        .outerjoin(token_sq, Company.id == token_sq.c.company_id)
        .outerjoin(run_sq, Company.id == run_sq.c.company_id),
        plan_sq,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get(
    "/overview",
    response_model=PlatformOverview,
    dependencies=[platform_admin_only],
    summary="Platform-wide aggregate stats",
)
async def get_platform_overview(
    db: AsyncSession = Depends(get_db),
) -> PlatformOverview:
    ms = _month_start()

    total_enterprises = int((await db.execute(select(func.count(Enterprise.id)))).scalar() or 0)
    active_enterprises = int(
        (
            await db.execute(
                select(func.count(Enterprise.id)).where(Enterprise.is_active == True)  # noqa: E712
            )
        ).scalar()
        or 0
    )
    total_companies = int((await db.execute(select(func.count(Company.id)))).scalar() or 0)
    active_companies = int(
        (
            await db.execute(
                select(func.count(Company.id)).where(Company.is_active == True)  # noqa: E712
            )
        ).scalar()
        or 0
    )
    total_users = int(
        (await db.execute(select(func.count(distinct(UserRole.user_id))))).scalar() or 0
    )
    runs_this_month = int(
        (
            await db.execute(select(func.count(AgentRun.id)).where(AgentRun.created_at >= ms))
        ).scalar()
        or 0
    )
    token_row = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(CompanyTokenUsage.prompt_tokens + CompanyTokenUsage.completion_tokens),
                    0,
                ).label("tokens"),
                func.coalesce(func.sum(CompanyTokenUsage.total_cost_usd), 0).label("cost"),
            ).where(CompanyTokenUsage.usage_date >= ms)
        )
    ).one()

    return PlatformOverview(
        total_enterprises=total_enterprises,
        active_enterprises=active_enterprises,
        total_companies=total_companies,
        active_companies=active_companies,
        total_users=total_users,
        agent_runs_this_month=runs_this_month,
        tokens_this_month=int(token_row.tokens),
        estimated_cost_usd=Decimal(str(token_row.cost or 0)),
    )


@router.get(
    "/companies",
    response_model=list[CompanyAdminRead],
    dependencies=[platform_admin_only],
    summary="All companies with usage stats",
)
async def list_all_companies(
    enterprise_id: UUID | None = Query(default=None),
    plan_tier: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> list[CompanyAdminRead]:
    ms = _month_start()
    stmt, plan_sq = _company_stats_stmt(ms)
    stmt = stmt.order_by(Company.name)

    if enterprise_id is not None:
        stmt = stmt.where(Company.enterprise_id == enterprise_id)
    if active_only:
        stmt = stmt.where(Company.is_active == True)  # noqa: E712
    if plan_tier is not None:
        stmt = stmt.where(func.coalesce(plan_sq.c.plan_tier, "free") == plan_tier)

    rows = (await db.execute(stmt)).all()
    return [
        CompanyAdminRead(
            id=r.id,
            name=r.name,
            slug=r.slug,
            enterprise_id=r.enterprise_id,
            enterprise_name=r.enterprise_name,
            is_active=r.is_active,
            plan_tier=r.plan_tier,
            user_count=int(r.user_count),
            system_count=int(r.system_count),
            tokens_this_month=int(r.tokens_this_month),
            runs_this_month=int(r.runs_this_month),
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/companies/{company_id}",
    response_model=CompanyAdminDetail,
    dependencies=[platform_admin_only],
    summary="Single company with usage history",
)
async def get_company_admin_detail(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CompanyAdminDetail:
    ms = _month_start()
    stmt, _ = _company_stats_stmt(ms)
    stmt = stmt.where(Company.id == company_id)

    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Fetch plan limits for the detail view
    plan = await UsageService(db).get_plan(company_id)

    # Fetch usage history (last 6 months)
    history_rows = await UsageService(db).get_usage_history(company_id, months=6)
    history = [
        MonthlyUsageSummary(
            year=h.year,
            month=h.month,
            total_tokens=h.total_tokens,
            agent_runs=h.agent_runs,
            estimated_cost_usd=h.estimated_cost_usd,
        )
        for h in history_rows
    ]

    return CompanyAdminDetail(
        id=row.id,
        name=row.name,
        slug=row.slug,
        enterprise_id=row.enterprise_id,
        enterprise_name=row.enterprise_name,
        industry=row.industry,
        is_active=row.is_active,
        plan_tier=row.plan_tier,
        monthly_token_limit=plan.monthly_token_limit if plan else None,
        monthly_run_limit=plan.monthly_agent_run_limit if plan else None,
        user_count=int(row.user_count),
        system_count=int(row.system_count),
        tokens_this_month=int(row.tokens_this_month),
        runs_this_month=int(row.runs_this_month),
        created_at=row.created_at,
        usage_history=history,
    )


@router.patch(
    "/companies/{company_id}/plan",
    response_model=PlanResponse,
    dependencies=[platform_admin_only],
    summary="Update a company's plan tier and limits",
)
async def update_company_plan(
    company_id: UUID,
    body: PlanPatchBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlanResponse:
    # Verify company exists
    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

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
    await db.refresh(plan)
    log.info(
        "admin.plan.updated",
        company_id=str(company_id),
        plan_tier=body.plan_tier,
    )
    await AuditService(db).log(
        event_type="plan.updated",
        actor_user_id=current_user.user.id,
        actor_email=current_user.user.email,
        company_id=company_id,
        resource_type="plan",
        resource_id=str(plan.id),
        changes={
            "after": {
                "plan_tier": body.plan_tier,
                "override_reason": body.override_reason,
            }
        },
        request=request,
    )
    return PlanResponse.model_validate(plan)
