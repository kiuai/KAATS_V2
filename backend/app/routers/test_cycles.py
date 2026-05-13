"""Test cycles router — system-scoped cycles, bulk-assign, submit result, execute-all."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import (
    Permission,
    any_authenticated,
    can_manage_content,
    can_run_agents,
    require_system_access,
)
from app.dependencies import get_db, get_current_user_id, get_current_company_id
from app.schemas.test_cycle import (
    TestAssignmentCreate,
    TestAssignmentRead,
    TestAssignmentUpdate,
    TestCycleCreate,
    TestCycleRead,
    TestCycleUpdate,
    TestExecutionRead,
    TestResultCreate,
    TestResultRead,
)
from app.services.test_cycle_service import TestCycleService

router = APIRouter(tags=["test_cycles"])


# ── Legacy execution endpoints (backwards compat) ─────────────────────────────

@router.get("/scripts/{script_id}/executions", response_model=list[TestExecutionRead], include_in_schema=False)
async def list_executions(
    script_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = any_authenticated,
) -> list[TestExecutionRead]:
    return await TestCycleService(db).list_for_script(script_id)


@router.get("/executions/{execution_id}", response_model=TestExecutionRead, include_in_schema=False)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = any_authenticated,
) -> TestExecutionRead:
    return await TestCycleService(db).get(execution_id)


@router.post("/executions/{execution_id}/rerun", response_model=TestExecutionRead, status_code=202, include_in_schema=False)
async def rerun_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = can_run_agents,
) -> TestExecutionRead:
    return await TestCycleService(db).rerun(execution_id)


@router.delete("/executions/{execution_id}", status_code=204, response_model=None, include_in_schema=False)
async def delete_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = can_manage_content,
) -> None:
    await TestCycleService(db).delete(execution_id)


# ── System-scoped cycles ──────────────────────────────────────────────────────

@router.get("/systems/{system_id}/test-cycles")
async def list_test_cycles(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.CYCLE_READ),
) -> list[dict]:
    return await TestCycleService(db).list_for_system(system_id)


@router.post("/systems/{system_id}/test-cycles", response_model=TestCycleRead, status_code=201)
async def create_test_cycle(
    system_id: UUID,
    body: TestCycleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.CYCLE_CREATE),
) -> TestCycleRead:
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await TestCycleService(db).create_cycle(
        system_id=system_id,
        body=body,
        company_id=company_id,
        created_by=user_id,
    )


# ── Cycle detail / update / cancel ────────────────────────────────────────────

@router.get("/test-cycles/{cycle_id}")
async def get_test_cycle(
    cycle_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    return await TestCycleService(db).get_cycle_detail(cycle_id)


@router.patch("/test-cycles/{cycle_id}", response_model=TestCycleRead)
async def update_test_cycle(
    cycle_id: UUID,
    body: TestCycleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TestCycleRead:
    return await TestCycleService(db).update_cycle(cycle_id, body)


@router.post("/test-cycles/{cycle_id}/cancel", response_model=TestCycleRead)
async def cancel_test_cycle(
    cycle_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = can_manage_content,
) -> TestCycleRead:
    return await TestCycleService(db).cancel_cycle(cycle_id)


# ── Assignments ───────────────────────────────────────────────────────────────

@router.post("/test-cycles/{cycle_id}/assignments", response_model=list[TestAssignmentRead], status_code=201)
async def bulk_assign(
    cycle_id: UUID,
    assignments: list[TestAssignmentCreate],
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TestAssignmentRead]:
    assigned_by = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await TestCycleService(db).bulk_assign(
        cycle_id=cycle_id,
        assignments_data=assignments,
        assigned_by=assigned_by,
        company_id=company_id,
    )


@router.get("/test-cycles/{cycle_id}/assignments", response_model=list[TestAssignmentRead])
async def list_assignments(
    cycle_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TestAssignmentRead]:
    return await TestCycleService(db).list_assignments(
        cycle_id=cycle_id,
        current_user=current_user,
    )


@router.patch("/test-cycles/{cycle_id}/assignments/{assignment_id}", response_model=TestAssignmentRead)
async def update_assignment(
    cycle_id: UUID,
    assignment_id: UUID,
    body: TestAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TestAssignmentRead:
    return await TestCycleService(db).update_assignment(cycle_id, assignment_id, body)


# ── Submit result ─────────────────────────────────────────────────────────────

@router.post("/test-cycles/{cycle_id}/assignments/{assignment_id}/result", response_model=TestResultRead, status_code=201)
async def submit_result(
    cycle_id: UUID,
    assignment_id: UUID,
    body: TestResultCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TestResultRead:
    executed_by = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await TestCycleService(db).submit_result(
        cycle_id=cycle_id,
        assignment_id=assignment_id,
        outcome=body.outcome.value if hasattr(body.outcome, "value") else body.outcome,
        actual_result=body.actual_result,
        notes=body.notes,
        executed_by=executed_by,
        company_id=company_id,
    )


# ── Execute all ───────────────────────────────────────────────────────────────

@router.post("/test-cycles/{cycle_id}/execute-all", status_code=202)
async def execute_all(
    cycle_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    company_id = get_current_company_id(request)
    triggered_by = get_current_user_id(request)
    return await TestCycleService(db).execute_all(
        cycle_id=cycle_id,
        company_id=company_id,
        triggered_by_user_id=triggered_by,
    )
