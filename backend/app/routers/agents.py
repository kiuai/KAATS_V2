from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_run_agents
from app.dependencies import get_db, get_current_user_id, get_current_company_id
from app.schemas.agent_run import AgentRunRead, AgentTriggerRequest
from app.services.agent_run_service import AgentRunService

router = APIRouter(tags=["agents"])


@router.post("/systems/{system_id}/agents/crawl", response_model=AgentRunRead, status_code=202, dependencies=[can_run_agents])
async def trigger_crawl(
    system_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AgentRunRead:
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await AgentRunService(db).trigger(
        agent_type="crawl",
        system_id=system_id,
        triggered_by_user_id=user_id,
        company_id=company_id,
    )


@router.post("/systems/{system_id}/agents/generate", response_model=AgentRunRead, status_code=202, dependencies=[can_run_agents])
async def trigger_generation(
    system_id: UUID,
    body: AgentTriggerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AgentRunRead:
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await AgentRunService(db).trigger(
        agent_type="generation",
        system_id=system_id,
        triggered_by_user_id=user_id,
        company_id=company_id,
        requirement_ids=body.requirement_ids,
        target_formats=body.target_formats,
        input_config=body.input_config,
    )


@router.post("/scripts/{script_id}/agents/execute", response_model=AgentRunRead, status_code=202, dependencies=[can_run_agents])
async def trigger_execution(
    script_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AgentRunRead:
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await AgentRunService(db).trigger(
        agent_type="execution",
        script_id=script_id,
        triggered_by_user_id=user_id,
        company_id=company_id,
    )


@router.get("/agent_runs", response_model=list[AgentRunRead], dependencies=[any_authenticated])
async def list_agent_runs(
    request: Request,
    agent_type: str | None = None,
    run_status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[AgentRunRead]:
    company_id = get_current_company_id(request)
    return await AgentRunService(db).list_runs(company_id=company_id, agent_type=agent_type, run_status=run_status)


@router.get("/agent_runs/{run_id}", response_model=AgentRunRead, dependencies=[any_authenticated])
async def get_agent_run(run_id: UUID, db: AsyncSession = Depends(get_db)) -> AgentRunRead:
    return await AgentRunService(db).get_run(run_id)


@router.get("/agent_runs/{run_id}/steps", dependencies=[any_authenticated])
async def get_run_steps(run_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    return await AgentRunService(db).get_steps_from_cosmos(run_id)


@router.delete("/agent_runs/{run_id}", status_code=204, response_model=None, dependencies=[can_run_agents])
async def cancel_agent_run(run_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await AgentRunService(db).cancel(run_id)


@router.get("/agent_runs/{run_id}/stream", dependencies=[any_authenticated])
async def stream_agent_run(run_id: UUID, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Server-Sent Events stream for live agent step output."""

    async def event_generator():
        service = AgentRunService(db)
        async for event in service.stream_steps(run_id):
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
