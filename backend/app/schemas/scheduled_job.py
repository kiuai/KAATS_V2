from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AgentType, ScheduleType


class ScheduledJobRead(BaseModel):
    id: UUID
    company_id: UUID
    system_id: UUID | None
    name: str
    description: str | None
    agent_type: str
    schedule_type: str
    cron_expression: str | None
    timezone: str
    run_at: datetime | None
    job_config: dict | None
    is_active: bool
    max_failures: int
    consecutive_failures: int
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduledJobCreate(BaseModel):
    system_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    agent_type: AgentType
    schedule_type: ScheduleType
    cron_expression: str | None = Field(default=None, min_length=9, max_length=100)
    timezone: str = Field(default="UTC", max_length=100)
    run_at: datetime | None = None
    job_config: dict | None = None
    is_active: bool = True
    max_failures: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_schedule(self) -> "ScheduledJobCreate":
        if self.schedule_type == ScheduleType.RECURRING and not self.cron_expression:
            raise ValueError("cron_expression is required for RECURRING jobs")
        if self.schedule_type == ScheduleType.ONE_SHOT and not self.run_at:
            raise ValueError("run_at is required for ONE_SHOT jobs")
        return self


class ScheduledJobUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    cron_expression: str | None = Field(default=None, min_length=9, max_length=100)
    timezone: str | None = Field(default=None, max_length=100)
    run_at: datetime | None = None
    job_config: dict | None = None
    is_active: bool | None = None
    max_failures: int | None = Field(default=None, ge=1, le=10)


class ScheduledJobRunRead(BaseModel):
    id: UUID
    job_id: UUID
    agent_run_id: UUID | None
    status: str
    scheduled_for: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failure_reason: str | None

    model_config = {"from_attributes": True}
