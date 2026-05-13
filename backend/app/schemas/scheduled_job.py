from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ScheduledJobRead(BaseModel):
    id: UUID
    company_id: UUID
    system_id: UUID
    agent_type: str
    cron_expression: str
    timezone: str
    is_enabled: bool
    max_failures: int
    consecutive_failures: int
    next_run_at: datetime
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduledJobCreate(BaseModel):
    system_id: UUID
    agent_type: str = Field(pattern=r"^(crawl|generation|execution)$")
    cron_expression: str = Field(min_length=9, max_length=100)
    timezone: str = Field(default="UTC", max_length=100)
    is_enabled: bool = True
    max_failures: int = Field(default=3, ge=1, le=10)


class ScheduledJobUpdate(BaseModel):
    cron_expression: str | None = Field(default=None, min_length=9, max_length=100)
    timezone: str | None = Field(default=None, max_length=100)
    is_enabled: bool | None = None
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
