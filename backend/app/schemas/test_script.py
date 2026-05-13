from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TestStepRead(BaseModel):
    id: UUID
    step_number: int
    action: str
    description: str
    expected_outcome: str | None
    parameters: dict | None

    model_config = {"from_attributes": True}


class TestCaseRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    stop_on_failure: bool
    order_index: int
    steps: list[TestStepRead] = []

    model_config = {"from_attributes": True}


class TestScriptRead(BaseModel):
    id: UUID
    requirement_id: UUID | None
    system_id: UUID
    company_id: UUID
    title: str
    format: str
    status: str
    created_at: datetime
    updated_at: datetime
    cases: list[TestCaseRead] = []

    model_config = {"from_attributes": True}


class TestScriptCreate(BaseModel):
    requirement_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    format: str = Field(
        default="playwright_python",
        pattern=r"^(playwright_python|gherkin|manual_steps|selenium_java|cypress_js)$",
    )


class TestScriptUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    status: str | None = Field(default=None, pattern=r"^(draft|approved|deprecated)$")
