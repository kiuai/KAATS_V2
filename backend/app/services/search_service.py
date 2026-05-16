"""Global search service — cross-entity full-text search.

Searches across: systems, requirements, test scripts, test cycles, agent runs.
Results are scoped to the caller's company_id (RLS is set by TenantMiddleware
but we also filter explicitly for safety).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class SearchService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def search(
        self,
        *,
        q: str,
        company_id: uuid.UUID,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return a flat list of search results across multiple entity types."""
        if not q or len(q.strip()) < 2:
            return []
        term = q.strip().lower()
        results: list[dict[str, Any]] = []

        results.extend(await self._search_systems(term, company_id, limit))
        results.extend(await self._search_requirements(term, company_id, limit))
        results.extend(await self._search_test_scripts(term, company_id, limit))
        results.extend(await self._search_test_cycles(term, company_id, limit))
        results.extend(await self._search_agent_runs(term, company_id, limit))

        # Sort by score (simple: exact match > starts-with > contains)
        def _score(r: dict) -> int:
            label = r.get("label", "").lower()
            if label == term:
                return 0
            if label.startswith(term):
                return 1
            return 2

        results.sort(key=_score)
        return results[:limit]

    async def _search_systems(
        self, term: str, company_id: uuid.UUID, limit: int
    ) -> list[dict[str, Any]]:
        from app.models.system import System

        result = await self._db.execute(
            select(System.id, System.name, System.description)
            .where(
                System.company_id == company_id,
                System.is_deleted == False,  # noqa: E712
                or_(
                    System.name.ilike(f"%{term}%"),
                    System.description.ilike(f"%{term}%"),
                ),
            )
            .limit(limit)
        )
        return [
            {
                "type": "system",
                "id": str(r.id),
                "label": r.name,
                "description": (r.description or "")[:120],
                "url": f"/systems/{r.id}",
            }
            for r in result.all()
        ]

    async def _search_requirements(
        self, term: str, company_id: uuid.UUID, limit: int
    ) -> list[dict[str, Any]]:
        from app.models.requirement import Requirement
        from app.models.system import System

        result = await self._db.execute(
            select(Requirement.id, Requirement.title, Requirement.system_id)
            .join(System, Requirement.system_id == System.id)
            .where(
                System.company_id == company_id,
                Requirement.is_deleted == False,  # noqa: E712
                Requirement.title.ilike(f"%{term}%"),
            )
            .limit(limit)
        )
        return [
            {
                "type": "requirement",
                "id": str(r.id),
                "label": r.title,
                "description": None,
                "url": f"/requirements/{r.id}",
            }
            for r in result.all()
        ]

    async def _search_test_scripts(
        self, term: str, company_id: uuid.UUID, limit: int
    ) -> list[dict[str, Any]]:
        from app.models.system import System
        from app.models.test_script import TestScript

        result = await self._db.execute(
            select(TestScript.id, TestScript.title, TestScript.system_id)
            .join(System, TestScript.system_id == System.id)
            .where(
                System.company_id == company_id,
                TestScript.is_deleted == False,  # noqa: E712
                TestScript.title.ilike(f"%{term}%"),
            )
            .limit(limit)
        )
        return [
            {
                "type": "test_script",
                "id": str(r.id),
                "label": r.title,
                "description": None,
                "url": f"/test-scripts/{r.id}",
            }
            for r in result.all()
        ]

    async def _search_test_cycles(
        self, term: str, company_id: uuid.UUID, limit: int
    ) -> list[dict[str, Any]]:
        from app.models.test_cycle import TestCycle

        result = await self._db.execute(
            select(TestCycle.id, TestCycle.name)
            .where(
                TestCycle.company_id == company_id,
                TestCycle.name.ilike(f"%{term}%"),
            )
            .limit(limit)
        )
        return [
            {
                "type": "test_cycle",
                "id": str(r.id),
                "label": r.name,
                "description": None,
                "url": f"/test-cycles/{r.id}",
            }
            for r in result.all()
        ]

    async def _search_agent_runs(
        self, term: str, company_id: uuid.UUID, limit: int
    ) -> list[dict[str, Any]]:
        from app.models.agent_run import AgentRun

        result = await self._db.execute(
            select(AgentRun.id, AgentRun.agent_type, AgentRun.status)
            .where(
                AgentRun.company_id == company_id,
                AgentRun.agent_type.ilike(f"%{term}%"),
            )
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "type": "agent_run",
                "id": str(r.id),
                "label": f"{r.agent_type} run",
                "description": r.status,
                "url": f"/agents/{r.id}",
            }
            for r in result.all()
        ]
