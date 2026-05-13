from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_manage_content, can_run_agents
from app.dependencies import get_db
from app.schemas.test_cycle import TestExecutionRead
from app.services.test_cycle_service import TestCycleService

router = APIRouter(tags=["test_cycles"])


@router.get("/scripts/{script_id}/executions", response_model=list[TestExecutionRead], dependencies=[any_authenticated])
async def list_executions(script_id: UUID, db: AsyncSession = Depends(get_db)) -> list[TestExecutionRead]:
    return await TestCycleService(db).list_for_script(script_id)


@router.get("/executions/{execution_id}", response_model=TestExecutionRead, dependencies=[any_authenticated])
async def get_execution(execution_id: UUID, db: AsyncSession = Depends(get_db)) -> TestExecutionRead:
    return await TestCycleService(db).get(execution_id)


@router.post("/executions/{execution_id}/rerun", response_model=TestExecutionRead, status_code=202, dependencies=[can_run_agents])
async def rerun_execution(execution_id: UUID, db: AsyncSession = Depends(get_db)) -> TestExecutionRead:
    return await TestCycleService(db).rerun(execution_id)


@router.delete("/executions/{execution_id}", status_code=204, dependencies=[can_manage_content])
async def delete_execution(execution_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await TestCycleService(db).delete(execution_id)
