from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cosmos import get_agent_runs_container
from app.models.agent_run import AgentRun
from app.schemas.agent_run import AgentRunRead


class AgentRunService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def trigger(
        self,
        agent_type: str,
        triggered_by: UUID,
        system_id: UUID | None = None,
        script_id: UUID | None = None,
        requirement_ids: list[UUID] | None = None,
        target_formats: list[str] | None = None,
    ) -> AgentRunRead:
        from app.worker.service_bus_worker import publish_agent_job

        run = AgentRun(
            agent_type=agent_type,
            system_id=system_id,
            triggered_by=triggered_by,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            status="running",
        )
        self._db.add(run)
        await self._db.flush()

        await publish_agent_job(
            run_id=run.id,
            agent_type=agent_type,
            system_id=system_id,
            script_id=script_id,
        )
        return AgentRunRead.model_validate(run)

    async def list_runs(
        self, agent_type: str | None = None, status: str | None = None
    ) -> list[AgentRunRead]:
        query = select(AgentRun)
        if agent_type:
            query = query.where(AgentRun.agent_type == agent_type)
        if status:
            query = query.where(AgentRun.status == status)
        result = await self._db.execute(query.order_by(AgentRun.started_at.desc()))
        return [AgentRunRead.model_validate(r) for r in result.scalars().all()]

    async def get_run(self, run_id: UUID) -> AgentRunRead:
        run = await self._db.get(AgentRun, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
        return AgentRunRead.model_validate(run)

    async def get_steps_from_cosmos(self, run_id: UUID) -> dict:
        run = await self._db.get(AgentRun, run_id)
        if not run or not run.cosmos_doc_id:
            return {"steps": []}
        container = get_agent_runs_container()
        try:
            doc = await container.read_item(run.cosmos_doc_id, partition_key=str(run.company_id))
            return {"steps": doc.get("steps", [])}
        except Exception:
            return {"steps": []}

    async def cancel(self, run_id: UUID) -> None:
        run = await self._db.get(AgentRun, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
        if run.status != "running":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only running agents can be cancelled",
            )
        run.status = "failed"
        await self._db.flush()

    async def stream_steps(self, run_id: UUID) -> AsyncGenerator[dict, None]:
        """Poll Cosmos DB for new steps and yield them as SSE events."""
        run = await self._db.get(AgentRun, run_id)
        if not run:
            yield {"type": "error", "data": {"message": "Run not found"}}
            return

        last_index = 0
        while run.status == "running":
            await asyncio.sleep(2)
            await self._db.refresh(run)
            if run.cosmos_doc_id:
                container = get_agent_runs_container()
                try:
                    doc = await container.read_item(
                        run.cosmos_doc_id, partition_key=str(run.company_id)
                    )
                    steps = doc.get("steps", [])
                    for step in steps[last_index:]:
                        yield {"type": "step", "data": step}
                    last_index = len(steps)
                except Exception:
                    pass

        yield {"type": "complete", "data": {"status": run.status}}
