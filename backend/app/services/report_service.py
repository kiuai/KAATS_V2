from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import CompanyTokenUsage
from app.models.requirement import Requirement
from app.models.test_script import TestScript


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def project_summary(self, system_id: UUID) -> dict:
        req_count = await self._db.scalar(
            select(func.count()).where(Requirement.system_id == system_id)
        )
        script_count = await self._db.scalar(
            select(func.count()).where(TestScript.system_id == system_id)
        )
        return {
            "system_id": str(system_id),
            "requirement_count": req_count or 0,
            "script_count": script_count or 0,
        }

    async def script_coverage(self, system_id: UUID) -> dict:
        total = await self._db.scalar(
            select(func.count()).where(Requirement.system_id == system_id)
        )
        covered = await self._db.scalar(
            select(func.count(Requirement.id.distinct()))
            .join(TestScript, TestScript.requirement_id == Requirement.id)
            .where(Requirement.system_id == system_id)
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
