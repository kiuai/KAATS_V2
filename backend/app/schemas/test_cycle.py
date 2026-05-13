from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import TestAssignmentStatus, TestCycleStatus, TestOutcome


class TestCycleRead(BaseModel):
    id: UUID
    system_id: UUID
    company_id: UUID
    name: str
    description: str | None
    status: str
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    lead_user_id: UUID | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestCycleCreate(BaseModel):
    system_id: UUID
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    lead_user_id: UUID | None = None


class TestCycleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: TestCycleStatus | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    lead_user_id: UUID | None = None


class TestAssignmentRead(BaseModel):
    id: UUID
    test_cycle_id: UUID
    test_script_id: UUID
    assigned_to: UUID
    assigned_by: UUID
    due_date: datetime | None
    status: str
    assigned_at: datetime

    model_config = {"from_attributes": True}


class TestAssignmentCreate(BaseModel):
    test_script_id: UUID
    assigned_to: UUID
    due_date: datetime | None = None


class TestAssignmentUpdate(BaseModel):
    status: TestAssignmentStatus | None = None
    due_date: datetime | None = None


class TestResultRead(BaseModel):
    id: UUID
    assignment_id: UUID
    test_script_id: UUID
    company_id: UUID
    executed_by: UUID
    execution_agent_run_id: UUID | None
    executed_at: datetime
    outcome: str
    actual_result: str | None
    defect_reference: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TestResultCreate(BaseModel):
    outcome: TestOutcome
    actual_result: str | None = None
    defect_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = None


# Legacy — used by existing test execution router
class StepResultRead(BaseModel):
    id: UUID
    step_id: UUID
    status: str
    actual_outcome: str | None
    failure_reason: str | None
    executed_at: datetime | None
    duration_ms: int | None

    model_config = {"from_attributes": True}


class TestExecutionRead(BaseModel):
    id: UUID
    script_id: UUID
    system_id: UUID
    company_id: UUID
    triggered_by: UUID | None
    status: str
    passed_count: int
    failed_count: int
    skipped_count: int
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    step_results: list[StepResultRead] = []

    model_config = {"from_attributes": True}
