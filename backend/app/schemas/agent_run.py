from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AgentRunStatus, AgentTriggerType, AgentType


class AgentToolCallRead(BaseModel):
    id: UUID
    agent_run_id: UUID
    tool_name: str
    tool_input: dict | None
    tool_output: dict | None
    duration_ms: int | None
    success: bool
    called_at: datetime

    model_config = {"from_attributes": True}


class AgentRunRead(BaseModel):
    id: UUID
    company_id: UUID
    system_id: UUID | None
    agent_type: str
    status: str
    trigger_type: str
    triggered_by_user_id: UUID | None
    scheduled_job_id: UUID | None
    service_bus_message_id: str | None
    input_config: dict | None
    output_summary: dict | None
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: Decimal | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRunWithToolCalls(AgentRunRead):
    tool_calls: list[AgentToolCallRead] = []


class AgentTriggerRequest(BaseModel):
    agent_type: AgentType
    system_id: UUID | None = None
    script_id: UUID | None = None
    requirement_ids: list[UUID] | None = None
    target_formats: list[str] | None = None
    input_config: dict | None = None


class AgentStepEvent(BaseModel):
    step_index: int
    thought: str | None
    tool: str | None
    tool_input: dict | None
    observation: str | None
    timestamp: datetime
    duration_ms: int | None
    tokens_this_step: dict | None
