"""Usage metering and quota enforcement.

Plan-tier defaults (used when no CompanyPlan row exists):

  Tier        Tokens/month   Runs/month   Systems   Users
  ───────     ────────────   ──────────   ───────   ─────
  free        500 000        20           3         10
  pro         5 000 000      200          20        50
  enterprise  unlimited      unlimited    unlimited unlimited
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, CompanyTokenUsage
from app.models.plan import CompanyPlan

log = structlog.get_logger(__name__)


# ── Plan-tier defaults ────────────────────────────────────────────────────────


@dataclass
class PlanDefaults:
    plan_tier: str
    monthly_token_limit: int | None
    monthly_agent_run_limit: int | None
    max_systems: int | None
    max_users: int | None
    max_concurrent_agents: int | None


_TIER_DEFAULTS: dict[str, PlanDefaults] = {
    "free": PlanDefaults(
        plan_tier="free",
        monthly_token_limit=500_000,
        monthly_agent_run_limit=20,
        max_systems=3,
        max_users=10,
        max_concurrent_agents=1,
    ),
    "pro": PlanDefaults(
        plan_tier="pro",
        monthly_token_limit=5_000_000,
        monthly_agent_run_limit=200,
        max_systems=20,
        max_users=50,
        max_concurrent_agents=3,
    ),
    "enterprise": PlanDefaults(
        plan_tier="enterprise",
        monthly_token_limit=None,
        monthly_agent_run_limit=None,
        max_systems=None,
        max_users=None,
        max_concurrent_agents=None,
    ),
}


# ── Response shapes ───────────────────────────────────────────────────────────


@dataclass
class QuotaStatus:
    plan_tier: str
    # Monthly token quota
    tokens_used: int
    tokens_limit: int | None
    tokens_pct: float | None  # 0–100, None if unlimited
    tokens_warning: bool  # > 80 %
    tokens_exceeded: bool  # >= 100 %
    # Monthly run quota
    runs_used: int
    runs_limit: int | None
    runs_pct: float | None
    runs_warning: bool
    runs_exceeded: bool
    # Structural
    max_systems: int | None
    max_users: int | None
    max_concurrent_agents: int | None
    # Billing
    estimated_cost_usd: Decimal


@dataclass
class MonthlyUsageRow:
    year: int
    month: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    agent_runs: int
    estimated_cost_usd: Decimal


# ── Service ───────────────────────────────────────────────────────────────────


class UsageService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Plan access ───────────────────────────────────────────────────────────

    async def get_plan(self, company_id: UUID) -> CompanyPlan | None:
        result = await self._db.execute(
            select(CompanyPlan).where(CompanyPlan.company_id == company_id)
        )
        return result.scalar_one_or_none()

    def _effective_limits(self, plan: CompanyPlan | None) -> PlanDefaults:
        """Merge stored plan row with tier defaults (stored columns win if set)."""
        tier = plan.plan_tier if plan else "free"
        defaults = _TIER_DEFAULTS.get(tier, _TIER_DEFAULTS["free"])

        if plan is None:
            return defaults

        return PlanDefaults(
            plan_tier=tier,
            monthly_token_limit=(
                plan.monthly_token_limit
                if plan.monthly_token_limit is not None
                else defaults.monthly_token_limit
            ),
            monthly_agent_run_limit=(
                plan.monthly_agent_run_limit
                if plan.monthly_agent_run_limit is not None
                else defaults.monthly_agent_run_limit
            ),
            max_systems=(
                plan.max_systems if plan.max_systems is not None else defaults.max_systems
            ),
            max_users=(plan.max_users if plan.max_users is not None else defaults.max_users),
            max_concurrent_agents=(
                plan.max_concurrent_agents
                if plan.max_concurrent_agents is not None
                else defaults.max_concurrent_agents
            ),
        )

    # ── Current period usage ──────────────────────────────────────────────────

    async def get_quota_status(self, company_id: UUID) -> QuotaStatus:
        plan = await self.get_plan(company_id)
        limits = self._effective_limits(plan)

        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

        # Token usage from company_token_usage (daily roll-ups)
        token_result = await self._db.execute(
            select(
                func.coalesce(func.sum(CompanyTokenUsage.prompt_tokens), 0).label("prompt"),
                func.coalesce(func.sum(CompanyTokenUsage.completion_tokens), 0).label("completion"),
                func.coalesce(func.sum(CompanyTokenUsage.total_cost_usd), 0).label("cost"),
            ).where(
                CompanyTokenUsage.company_id == company_id,
                CompanyTokenUsage.usage_date >= month_start,
            )
        )
        row = token_result.one()
        prompt_tokens = int(row.prompt)
        completion_tokens = int(row.completion)
        tokens_used = prompt_tokens + completion_tokens
        estimated_cost = Decimal(str(row.cost or 0))

        # Agent run count
        runs_result = await self._db.execute(
            select(func.count(AgentRun.id)).where(
                AgentRun.company_id == company_id,
                AgentRun.created_at >= month_start,
            )
        )
        runs_used = int(runs_result.scalar() or 0)

        # Compute percentages
        def pct(used: int, limit: int | None) -> float | None:
            if limit is None:
                return None
            return round(used / limit * 100, 1) if limit > 0 else 100.0

        tokens_pct = pct(tokens_used, limits.monthly_token_limit)
        runs_pct = pct(runs_used, limits.monthly_agent_run_limit)

        return QuotaStatus(
            plan_tier=limits.plan_tier,
            tokens_used=tokens_used,
            tokens_limit=limits.monthly_token_limit,
            tokens_pct=tokens_pct,
            tokens_warning=tokens_pct is not None and tokens_pct >= 80,
            tokens_exceeded=tokens_pct is not None and tokens_pct >= 100,
            runs_used=runs_used,
            runs_limit=limits.monthly_agent_run_limit,
            runs_pct=runs_pct,
            runs_warning=runs_pct is not None and runs_pct >= 80,
            runs_exceeded=runs_pct is not None and runs_pct >= 100,
            max_systems=limits.max_systems,
            max_users=limits.max_users,
            max_concurrent_agents=limits.max_concurrent_agents,
            estimated_cost_usd=estimated_cost,
        )

    # ── Monthly history ───────────────────────────────────────────────────────

    async def get_usage_history(self, company_id: UUID, months: int = 6) -> list[MonthlyUsageRow]:
        """Return up to `months` calendar months of token + run data."""
        # Token roll-ups
        token_rows = await self._db.execute(
            select(
                func.year(CompanyTokenUsage.usage_date).label("yr"),
                func.month(CompanyTokenUsage.usage_date).label("mo"),
                func.sum(CompanyTokenUsage.prompt_tokens).label("prompt"),
                func.sum(CompanyTokenUsage.completion_tokens).label("completion"),
                func.sum(CompanyTokenUsage.total_cost_usd).label("cost"),
            )
            .where(CompanyTokenUsage.company_id == company_id)
            .group_by(
                func.year(CompanyTokenUsage.usage_date),
                func.month(CompanyTokenUsage.usage_date),
            )
            .order_by(
                func.year(CompanyTokenUsage.usage_date).desc(),
                func.month(CompanyTokenUsage.usage_date).desc(),
            )
            .limit(months)
        )
        token_by_ym: dict[tuple[int, int], dict] = {}
        for r in token_rows:
            key = (int(r.yr), int(r.mo))
            token_by_ym[key] = {
                "prompt": int(r.prompt or 0),
                "completion": int(r.completion or 0),
                "cost": Decimal(str(r.cost or 0)),
            }

        # Run counts
        run_rows = await self._db.execute(
            select(
                func.year(AgentRun.created_at).label("yr"),
                func.month(AgentRun.created_at).label("mo"),
                func.count(AgentRun.id).label("cnt"),
            )
            .where(AgentRun.company_id == company_id)
            .group_by(
                func.year(AgentRun.created_at),
                func.month(AgentRun.created_at),
            )
        )
        run_by_ym: dict[tuple[int, int], int] = {
            (int(r.yr), int(r.mo)): int(r.cnt) for r in run_rows
        }

        result: list[MonthlyUsageRow] = []
        for (yr, mo), td in sorted(token_by_ym.items(), reverse=True):
            result.append(
                MonthlyUsageRow(
                    year=yr,
                    month=mo,
                    prompt_tokens=td["prompt"],
                    completion_tokens=td["completion"],
                    total_tokens=td["prompt"] + td["completion"],
                    agent_runs=run_by_ym.get((yr, mo), 0),
                    estimated_cost_usd=td["cost"],
                )
            )
        return result[:months]

    # ── Quota enforcement ─────────────────────────────────────────────────────

    async def assert_agent_run_allowed(self, company_id: UUID) -> None:
        """Raise HTTP 429 if the company has exceeded its monthly quotas.

        Called by AgentDispatcher before creating a new AgentRun.
        Only blocks on hard limits (100 %); warnings (80 %) are advisory.
        """
        qs = await self.get_quota_status(company_id)

        if qs.runs_exceeded:
            log.warning(
                "usage.quota.runs_exceeded",
                company_id=str(company_id),
                runs_used=qs.runs_used,
                runs_limit=qs.runs_limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "QUOTA_EXCEEDED",
                    "message": (
                        f"Monthly agent run quota exceeded "
                        f"({qs.runs_used}/{qs.runs_limit} runs used). "
                        "Upgrade your plan or wait until next month."
                    ),
                    "quota_type": "agent_runs",
                    "used": qs.runs_used,
                    "limit": qs.runs_limit,
                },
            )

        if qs.tokens_exceeded:
            log.warning(
                "usage.quota.tokens_exceeded",
                company_id=str(company_id),
                tokens_used=qs.tokens_used,
                tokens_limit=qs.tokens_limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "QUOTA_EXCEEDED",
                    "message": (
                        f"Monthly token quota exceeded "
                        f"({qs.tokens_used:,}/{qs.tokens_limit:,} tokens used). "
                        "Upgrade your plan or wait until next month."
                    ),
                    "quota_type": "tokens",
                    "used": qs.tokens_used,
                    "limit": qs.tokens_limit,
                },
            )

    # ── Plan management (platform admin) ─────────────────────────────────────

    async def upsert_plan(
        self,
        company_id: UUID,
        plan_tier: str,
        monthly_token_limit: int | None = None,
        monthly_agent_run_limit: int | None = None,
        max_systems: int | None = None,
        max_users: int | None = None,
        max_concurrent_agents: int | None = None,
        override_reason: str | None = None,
    ) -> CompanyPlan:
        if plan_tier not in _TIER_DEFAULTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown plan tier '{plan_tier}'. Valid: {list(_TIER_DEFAULTS)}",
            )
        plan = await self.get_plan(company_id)
        if plan is None:
            plan = CompanyPlan(company_id=company_id)
            self._db.add(plan)

        plan.plan_tier = plan_tier
        if monthly_token_limit is not None:
            plan.monthly_token_limit = monthly_token_limit
        if monthly_agent_run_limit is not None:
            plan.monthly_agent_run_limit = monthly_agent_run_limit
        if max_systems is not None:
            plan.max_systems = max_systems
        if max_users is not None:
            plan.max_users = max_users
        if max_concurrent_agents is not None:
            plan.max_concurrent_agents = max_concurrent_agents
        if override_reason is not None:
            plan.override_reason = override_reason

        await self._db.flush()
        log.info(
            "usage.plan.updated",
            company_id=str(company_id),
            plan_tier=plan_tier,
        )
        return plan
