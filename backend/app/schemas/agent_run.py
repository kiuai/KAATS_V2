from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunRead(BaseModel):
    id: UUID
    company_id: UUID
    system_id: UUID | None
    agent_type: str
    status: str
    prompt_tokens: int
    completion_tokens: int
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    execution_id: UUID | None
    cosmos_doc_id: str | None

    model_config = {"from_attributes": True}


class AgentTriggerRequest(BaseModel):
    agent_type: str = Field(pattern=r"^(crawl|generation|execution)$")
    system_id: UUID | None = None
    script_id: UUID | None = None
    requirement_ids: list[UUID] | None = None
    target_formats: list[str] | None = None


class AgentStepEvent(BaseModel):
    step_index: int
    thought: str | None
    tool: str | None
    tool_input: dict | None
    observation: str | None
    timestamp: datetime
    duration_ms: int | None
    tokens_this_step: dict | None
