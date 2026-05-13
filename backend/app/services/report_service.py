"""Report service — coverage-by-domain, execution history, cycle summary, company overview, AI usage."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, CompanyTokenUsage
from app.models.enums import (
    AgentType,
    RequirementStatus,
    TestAssignmentStatus,
    TestCycleStatus,
    TestScriptStatus,
)
from app.models.requirement import Requirement
from app.models.test_cycle import TestAssignment, TestCycle
from app.models.test_script import TestScript

log = structlog.get_logger(__name__)


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Legacy (backwards compat) ─────────────────────────────────────────────

    async def project_summary(self, system_id: UUID) -> dict:
        req_count = await self._db.scalar(
            select(func.count()).where(
                Requirement.system_id == system_id,
                Requirement.deleted_at.is_(None),
            )
        )
        script_count = await self._db.scalar(
            select(func.count()).where(
                TestScript.system_id == system_id,
                TestScript.deleted_at.is_(None),
            )
        )
        return {
            "system_id": str(system_id),
            "requirement_count": req_count or 0,
            "script_count": script_count or 0,
        }

    async def script_coverage(self, system_id: UUID) -> dict:
        total = await self._db.scalar(
            select(func.count()).where(
                Requirement.system_id == system_id,
                Requirement.deleted_at.is_(None),
            )
        )
        covered = await self._db.scalar(
            select(func.count(Requirement.id.distinct()))
            .join(TestScript, TestScript.requirement_id == Requirement.id)
            .where(
                Requirement.system_id == system_id,
                Requirement.deleted_at.is_(None),
            )
        )
        return {
            "system_id": str(system_id),
            "total_requirements": total or 0,
            "requirements_with_scripts": covered or 0,
            "coverage_percent": round((covered or 0) / (total or 1) * 100, 1),
        }

    async def token_usage(
        self,
        agent_type: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> dict:
        query = select(CompanyTokenUsage)
        if agent_type:
            query = query.where(CompanyTokenUsage.agent_type == agent_type)
        result = await self._db.execute(query)
        rows = result.scalars().all()
        return {
            "usage": [
                {
                    "agent_type": r.agent_type,
                    "usage_date": r.usage_date.isoformat(),
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                }
                for r in rows
            ]
        }

    # ── New report endpoints ──────────────────────────────────────────────────

    async def coverage_by_domain(self, system_id: UUID) -> dict:
        """
        Requirement and script coverage broken down by business_domain.
        Returns a list of { domain, requirement_count, script_count, approved_script_count, coverage_pct }.
        """
        # All requirements, grouped by domain
        req_rows = await self._db.execute(
            select(
                Requirement.business_domain,
                func.count(Requirement.id).label("req_count"),
            )
            .where(
                Requirement.system_id == system_id,
                Requirement.deleted_at.is_(None),
            )
            .group_by(Requirement.business_domain)
        )
        req_by_domain: dict[str | None, int] = {
            row.business_domain: row.req_count for row in req_rows
        }

        # All scripts (approved), grouped by domain
        script_rows = await self._db.execute(
            select(
                TestScript.business_domain,
                func.count(TestScript.id).label("script_count"),
            )
            .where(
                TestScript.system_id == system_id,
                TestScript.deleted_at.is_(None),
            )
            .group_by(TestScript.business_domain)
        )
        scripts_by_domain: dict[str | None, int] = {
            row.business_domain: row.script_count for row in script_rows
        }

        approved_rows = await self._db.execute(
            select(
                TestScript.business_domain,
                func.count(TestScript.id).label("approved_count"),
            )
            .where(
                TestScript.system_id == system_id,
                TestScript.status == TestScriptStatus.APPROVED.value,
                TestScript.deleted_at.is_(None),
            )
            .group_by(TestScript.business_domain)
        )
        approved_by_domain: dict[str | None, int] = {
            row.business_domain: row.approved_count for row in approved_rows
        }

        all_domains: set[str | None] = (
            set(req_by_domain.keys())
            | set(scripts_by_domain.keys())
        )

        breakdown = []
        for domain in sorted(all_domains, key=lambda d: d or ""):
            req_count = req_by_domain.get(domain, 0)
            script_count = scripts_by_domain.get(domain, 0)
            approved = approved_by_domain.get(domain, 0)
            coverage_pct = round(approved / req_count * 100, 1) if req_count > 0 else 0.0
            breakdown.append({
                "domain": domain,
                "requirement_count": req_count,
                "script_count": script_count,
                "approved_script_count": approved,
                "coverage_pct": coverage_pct,
            })

        return {
            "system_id": str(system_id),
            "breakdown": breakdown,
        }

    async def execution_history(
        self,
        system_id: UUID,
        limit: int = 50,
        days: int = 30,
    ) -> dict:
        """
        Recent AgentRun execution records for a system.
        Returns the most recent `limit` runs within the last `days` days.
        """
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        result = await self._db.execute(
            select(AgentRun)
            .where(
                AgentRun.system_id == system_id,
                AgentRun.agent_type == AgentType.EXECUTION.value,
                AgentRun.created_at >= since,
            )
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        runs = result.scalars().all()
        return {
            "system_id": str(system_id),
            "executions": [
                {
                    "id": str(r.id),
                    "status": r.status,
                    "trigger_type": r.trigger_type,
                    "triggered_by_user_id": str(r.triggered_by_user_id) if r.triggered_by_user_id else None,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "error_message": r.error_message,
                }
                for r in runs
            ],
        }

    async def cycle_summary(self, cycle_id: UUID) -> dict:
        """
        Pass/fail/blocked/skipped/pending counts for a test cycle.
        """
        cycle = await self._db.get(TestCycle, cycle_id)
        if not cycle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test cycle not found",
            )

        result = await self._db.execute(
            select(
                TestAssignment.status,
                func.count(TestAssignment.id).label("cnt"),
            )
            .where(TestAssignment.test_cycle_id == cycle_id)
            .group_by(TestAssignment.status)
        )
        counts: dict[str, int] = {row.status: row.cnt for row in result}

        total = sum(counts.values())
        passed = counts.get(TestAssignmentStatus.PASSED.value, 0)
        failed = counts.get(TestAssignmentStatus.FAILED.value, 0)
        blocked = counts.get(TestAssignmentStatus.BLOCKED.value, 0)
        skipped = counts.get(TestAssignmentStatus.SKIPPED.value, 0)
        pending = counts.get(TestAssignmentStatus.PENDING.value, 0)
        in_progress = counts.get(TestAssignmentStatus.IN_PROGRESS.value, 0)

        pass_rate = round(passed / total * 100, 1) if total > 0 else 0.0

        return {
            "cycle_id": str(cycle_id),
            "cycle_name": cycle.name,
            "cycle_status": cycle.status,
            "total": total,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "skipped": skipped,
            "pending": pending,
            "in_progress": in_progress,
            "pass_rate": pass_rate,
        }

    async def company_overview(self, company_id: UUID) -> dict:
        """
        High-level stats across the entire company:
        system count, requirement count, script count, active cycles.
        """
        from app.models.system import System
        from app.models.tenant import Company

        company = await self._db.get(Company, company_id)
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        system_count = await self._db.scalar(
            select(func.count()).where(
                System.company_id == company_id,
                System.is_deleted == False,  # noqa: E712
            )
        ) or 0

        req_count = await self._db.scalar(
            select(func.count()).where(
                Requirement.company_id == company_id,
                Requirement.deleted_at.is_(None),
            )
        ) or 0

        script_count = await self._db.scalar(
            select(func.count()).where(
                TestScript.company_id == company_id,
                TestScript.deleted_at.is_(None),
            )
        ) or 0

        approved_script_count = await self._db.scalar(
            select(func.count()).where(
                TestScript.company_id == company_id,
                TestScript.status == TestScriptStatus.APPROVED.value,
                TestScript.deleted_at.is_(None),
            )
        ) or 0

        active_cycle_count = await self._db.scalar(
            select(func.count()).where(
                TestCycle.company_id == company_id,
                TestCycle.status.in_([
                    TestCycleStatus.PLANNED.value,
                    TestCycleStatus.IN_PROGRESS.value,
                ]),
            )
        ) or 0

        return {
            "company_id": str(company_id),
            "system_count": system_count,
            "requirement_count": req_count,
            "script_count": script_count,
            "approved_script_count": approved_script_count,
            "active_cycle_count": active_cycle_count,
        }

    async def ai_usage(
        self,
        company_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        agent_type: str | None = None,
    ) -> dict:
        """
        AI token usage for a company, with optional date range and agent type filters.
        Returns per-day aggregates and a grand total.
        """
        q = select(
            AgentRun.agent_type,
            func.cast(AgentRun.created_at, type_=AgentRun.created_at.type).label("day"),
            func.sum(AgentRun.prompt_tokens).label("prompt_tokens"),
            func.sum(AgentRun.completion_tokens).label("completion_tokens"),
            func.sum(AgentRun.prompt_tokens + AgentRun.completion_tokens).label("total_tokens"),
        ).where(AgentRun.company_id == company_id)

        if agent_type:
            q = q.where(AgentRun.agent_type == agent_type)
        if date_from:
            q = q.where(AgentRun.created_at >= date_from)
        if date_to:
            q = q.where(AgentRun.created_at <= date_to)

        # Group by day (date portion) and agent_type
        q = q.group_by(
            AgentRun.agent_type,
            func.cast(AgentRun.created_at, type_=AgentRun.created_at.type),
        ).order_by(AgentRun.created_at.desc())

        result = await self._db.execute(q)
        rows = result.all()

        total_prompt = 0
        total_completion = 0
        breakdown = []
        for row in rows:
            p = int(row.prompt_tokens or 0)
            c = int(row.completion_tokens or 0)
            total_prompt += p
            total_completion += c
            breakdown.append({
                "agent_type": row.agent_type,
                "prompt_tokens": p,
                "completion_tokens": c,
                "total_tokens": p + c,
            })

        return {
            "company_id": str(company_id),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "breakdown": breakdown,
        }
