from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
