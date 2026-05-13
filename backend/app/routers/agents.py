from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import (
    Permission,
    any_authenticated,
    require_system_access,
)
from app.dependencies import get_current_company_id, get_db
from app.models.enums import AgentRunStatus
from app.schemas.agent_run import AgentRunRead, AgentRunWithToolCalls
from app.services.agent_dispatcher import AgentDispatcher
from app.services.agent_run_service import AgentRunService

router = APIRouter(tags=["agents"])


# ── Request schemas ───────────────────────────────────────────────────────────


class CrawlTriggerRequest(BaseModel):
    base_url: str
    max_pages: int | None = None


class GenerationTriggerRequest(BaseModel):
    requirement_ids: list[UUID]
    target_formats: list[str] = ["playwright_python"]


class ExecutionTriggerRequest(BaseModel):
    script_id: UUID


# ── Agent trigger endpoints ───────────────────────────────────────────────────


@router.post(
    "/systems/{system_id}/agents/crawl",
    response_model=AgentRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_crawl(
    system_id: UUID,
    body: CrawlTriggerRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _system: object = require_system_access(Permission.AGENT_CRAWL),
) -> AgentRunRead:
    """
    Trigger a crawl agent run for the given system.
    The agent will launch in the background; poll the returned run_id for status.
    """
    company_id = get_current_company_id(request)
    dispatcher = AgentDispatcher(db)
    run = await dispatcher.dispatch_crawl(
        company_id=company_id,
        system_id=system_id,
        base_url=body.base_url,
        max_pages=body.max_pages,
        triggered_by_user_id=current_user.user.id,
    )
    return AgentRunRead.model_validate(run)


@router.post(
    "/systems/{system_id}/agents/generate",
    response_model=AgentRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_generation(
    system_id: UUID,
    body: GenerationTriggerRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _system: object = require_system_access(Permission.AGENT_GENERATE),
) -> AgentRunRead:
    """
    Trigger a test-script generation run for the given requirements.
    Requires at least one requirement_id.
    """
    if not body.requirement_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="requirement_ids must not be empty",
        )
    company_id = get_current_company_id(request)
    dispatcher = AgentDispatcher(db)
    run = await dispatcher.dispatch_generation(
        company_id=company_id,
        system_id=system_id,
        requirement_ids=body.requirement_ids,
        target_formats=body.target_formats,
        triggered_by_user_id=current_user.user.id,
    )
    return AgentRunRead.model_validate(run)


@router.post(
    "/systems/{system_id}/agents/execute",
    response_model=AgentRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_execution(
    system_id: UUID,
    body: ExecutionTriggerRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _system: object = require_system_access(Permission.AGENT_EXECUTE),
) -> AgentRunRead:
    """
    Trigger an execution run for the given test script.
    The script must belong to the specified system.
    """
    company_id = get_current_company_id(request)
    dispatcher = AgentDispatcher(db)
    run = await dispatcher.dispatch_execution(
        company_id=company_id,
        system_id=system_id,
        script_id=body.script_id,
        triggered_by_user_id=current_user.user.id,
    )
    return AgentRunRead.model_validate(run)


# ── Agent run query endpoints ─────────────────────────────────────────────────


@router.get(
    "/systems/{system_id}/agent-runs",
    response_model=list[AgentRunRead],
    dependencies=[any_authenticated],
)
async def list_system_agent_runs(
    system_id: UUID,
    agent_type: str | None = None,
    run_status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[AgentRunRead]:
    """Return all agent runs scoped to a specific system."""
    return await AgentRunService(db).list_runs(
        system_id=system_id,
        agent_type=agent_type,
        run_status=run_status,
    )


@router.get(
    "/agent-runs",
    response_model=list[AgentRunRead],
    dependencies=[any_authenticated],
)
async def list_agent_runs(
    request: Request,
    agent_type: str | None = None,
    run_status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[AgentRunRead]:
    """Return all agent runs for the current company."""
    company_id = get_current_company_id(request)
    return await AgentRunService(db).list_runs(
        company_id=company_id,
        agent_type=agent_type,
        run_status=run_status,
    )


@router.get(
    "/agent-runs/{run_id}",
    response_model=AgentRunWithToolCalls,
    dependencies=[any_authenticated],
)
async def get_agent_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AgentRunWithToolCalls:
    """Return a single agent run with its tool-call log."""
    return await AgentRunService(db).get_run_with_tool_calls(run_id)


@router.get(
    "/agent-runs/{run_id}/steps",
    dependencies=[any_authenticated],
)
async def get_run_steps(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch the agent's step log from Cosmos DB."""
    return await AgentRunService(db).get_steps_from_cosmos(run_id)


@router.delete(
    "/agent-runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[any_authenticated],
)
async def cancel_agent_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Cancel a pending or running agent run.
    The worker checks for cancellation at each iteration boundary.
    """
    await AgentRunService(db).cancel(run_id)


@router.get(
    "/agent-runs/{run_id}/stream",
    dependencies=[any_authenticated],
)
async def stream_agent_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Server-Sent Events stream of live agent steps.
    The client should close the connection on the ``complete`` event.
    """

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
