"""Unit tests for UsageService — plan defaults, quota math, and enforcement.

These tests exercise the pure logic of UsageService without touching a real
database.  The DB calls are replaced with mocks.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.plan import CompanyPlan
from app.services.usage_service import (
    QuotaStatus,
    UsageService,
    _TIER_DEFAULTS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_plan(
    tier: str = "free",
    token_limit: int | None = None,
    run_limit: int | None = None,
) -> CompanyPlan:
    plan = MagicMock(spec=CompanyPlan)
    plan.plan_tier = tier
    plan.monthly_token_limit = token_limit
    plan.monthly_agent_run_limit = run_limit
    plan.max_systems = None
    plan.max_users = None
    plan.max_concurrent_agents = None
    return plan


def _make_service() -> UsageService:
    db = AsyncMock()
    return UsageService(db)


# ── Plan tier defaults ────────────────────────────────────────────────────────


class TestPlanDefaults:
    def test_free_tier_has_token_limit(self):
        assert _TIER_DEFAULTS["free"].monthly_token_limit == 500_000

    def test_free_tier_has_run_limit(self):
        assert _TIER_DEFAULTS["free"].monthly_agent_run_limit == 20

    def test_pro_tier_has_higher_limits(self):
        assert _TIER_DEFAULTS["pro"].monthly_token_limit > _TIER_DEFAULTS["free"].monthly_token_limit
        assert _TIER_DEFAULTS["pro"].monthly_agent_run_limit > _TIER_DEFAULTS["free"].monthly_agent_run_limit

    def test_enterprise_tier_is_unlimited(self):
        assert _TIER_DEFAULTS["enterprise"].monthly_token_limit is None
        assert _TIER_DEFAULTS["enterprise"].monthly_agent_run_limit is None

    def test_all_tiers_present(self):
        assert {"free", "pro", "enterprise"}.issubset(_TIER_DEFAULTS.keys())


# ── Effective limits (plan row overrides) ─────────────────────────────────────


class TestEffectiveLimits:
    def test_no_plan_row_uses_free_defaults(self):
        svc = _make_service()
        limits = svc._effective_limits(None)
        assert limits.plan_tier == "free"
        assert limits.monthly_token_limit == 500_000

    def test_plan_row_without_overrides_uses_tier_defaults(self):
        svc = _make_service()
        plan = _make_plan(tier="pro")
        limits = svc._effective_limits(plan)
        assert limits.monthly_token_limit == 5_000_000

    def test_custom_token_limit_overrides_tier_default(self):
        svc = _make_service()
        plan = _make_plan(tier="free", token_limit=999_000)
        limits = svc._effective_limits(plan)
        assert limits.monthly_token_limit == 999_000

    def test_custom_run_limit_overrides_tier_default(self):
        svc = _make_service()
        plan = _make_plan(tier="pro", run_limit=50)
        limits = svc._effective_limits(plan)
        assert limits.monthly_agent_run_limit == 50

    def test_enterprise_plan_row_without_overrides_is_unlimited(self):
        svc = _make_service()
        plan = _make_plan(tier="enterprise")
        limits = svc._effective_limits(plan)
        assert limits.monthly_token_limit is None
        assert limits.monthly_agent_run_limit is None

    def test_unknown_tier_falls_back_to_free(self):
        svc = _make_service()
        plan = _make_plan(tier="mystery_tier")
        limits = svc._effective_limits(plan)
        assert limits.monthly_token_limit == 500_000


# ── Quota status calculation ──────────────────────────────────────────────────


class TestQuotaStatus:
    def _quota(
        self,
        *,
        plan: CompanyPlan | None = None,
        tokens_used: int = 0,
        runs_used: int = 0,
    ) -> QuotaStatus:
        """Build a QuotaStatus directly via _effective_limits and pure math."""
        svc = _make_service()
        limits = svc._effective_limits(plan)

        def pct(used: int, limit: int | None) -> float | None:
            if limit is None:
                return None
            return round(used / limit * 100, 1) if limit > 0 else 100.0

        tp = pct(tokens_used, limits.monthly_token_limit)
        rp = pct(runs_used, limits.monthly_agent_run_limit)

        return QuotaStatus(
            plan_tier=limits.plan_tier,
            tokens_used=tokens_used,
            tokens_limit=limits.monthly_token_limit,
            tokens_pct=tp,
            tokens_warning=tp is not None and tp >= 80,
            tokens_exceeded=tp is not None and tp >= 100,
            runs_used=runs_used,
            runs_limit=limits.monthly_agent_run_limit,
            runs_pct=rp,
            runs_warning=rp is not None and rp >= 80,
            runs_exceeded=rp is not None and rp >= 100,
            max_systems=limits.max_systems,
            max_users=limits.max_users,
            max_concurrent_agents=limits.max_concurrent_agents,
            estimated_cost_usd=Decimal("0"),
        )

    def test_zero_usage_is_not_warning(self):
        qs = self._quota()
        assert not qs.tokens_warning
        assert not qs.runs_warning

    def test_80_pct_tokens_triggers_warning(self):
        qs = self._quota(tokens_used=400_000)  # 80% of 500k free limit
        assert qs.tokens_warning
        assert not qs.tokens_exceeded

    def test_100_pct_tokens_triggers_exceeded(self):
        qs = self._quota(tokens_used=500_000)
        assert qs.tokens_exceeded

    def test_over_100_pct_still_exceeded(self):
        qs = self._quota(tokens_used=600_000)
        assert qs.tokens_exceeded

    def test_80_pct_runs_triggers_warning(self):
        qs = self._quota(runs_used=16)  # 80% of 20 free limit
        assert qs.runs_warning
        assert not qs.runs_exceeded

    def test_enterprise_unlimited_never_warns(self):
        plan = _make_plan(tier="enterprise")
        qs = self._quota(plan=plan, tokens_used=100_000_000, runs_used=99_999)
        assert qs.tokens_pct is None
        assert qs.runs_pct is None
        assert not qs.tokens_warning
        assert not qs.runs_warning
        assert not qs.tokens_exceeded
        assert not qs.runs_exceeded

    def test_pct_rounds_to_one_decimal(self):
        # 1 / 3 = 33.333...
        plan = _make_plan(tier="free", token_limit=3)
        qs = self._quota(plan=plan, tokens_used=1)
        assert qs.tokens_pct == 33.3

    def test_zero_limit_shows_100_pct(self):
        plan = _make_plan(tier="free", token_limit=0)
        qs = self._quota(plan=plan, tokens_used=0)
        assert qs.tokens_pct == 100.0
        assert qs.tokens_exceeded


# ── assert_agent_run_allowed ──────────────────────────────────────────────────


class TestAssertAgentRunAllowed:
    async def _run_check(
        self, *, tokens_used: int = 0, runs_used: int = 0, tier: str = "free"
    ) -> None:
        plan = _make_plan(tier=tier)
        svc = _make_service()

        async def fake_quota_status(company_id):
            from app.services.usage_service import QuotaStatus
            limits = svc._effective_limits(plan)

            def pct(u, l):
                return round(u / l * 100, 1) if l else 100.0

            tp = pct(tokens_used, limits.monthly_token_limit) if limits.monthly_token_limit else None
            rp = pct(runs_used, limits.monthly_agent_run_limit) if limits.monthly_agent_run_limit else None
            return QuotaStatus(
                plan_tier=tier,
                tokens_used=tokens_used,
                tokens_limit=limits.monthly_token_limit,
                tokens_pct=tp,
                tokens_warning=tp is not None and tp >= 80,
                tokens_exceeded=tp is not None and tp >= 100,
                runs_used=runs_used,
                runs_limit=limits.monthly_agent_run_limit,
                runs_pct=rp,
                runs_warning=rp is not None and rp >= 80,
                runs_exceeded=rp is not None and rp >= 100,
                max_systems=limits.max_systems,
                max_users=limits.max_users,
                max_concurrent_agents=limits.max_concurrent_agents,
                estimated_cost_usd=Decimal("0"),
            )

        svc.get_quota_status = fake_quota_status
        await svc.assert_agent_run_allowed(uuid4())

    async def test_within_limits_does_not_raise(self):
        await self._run_check(tokens_used=100_000, runs_used=5)

    async def test_token_exceeded_raises_429(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await self._run_check(tokens_used=500_001)
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["code"] == "QUOTA_EXCEEDED"
        assert exc_info.value.detail["quota_type"] == "tokens"

    async def test_runs_exceeded_raises_429(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await self._run_check(runs_used=21)
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["quota_type"] == "agent_runs"

    async def test_warning_level_does_not_raise(self):
        # 81% of tokens — warning but not hard block
        await self._run_check(tokens_used=405_000)  # 81% of 500k

    async def test_enterprise_tier_never_raises(self):
        await self._run_check(tokens_used=999_999_999, runs_used=999_999, tier="enterprise")
