from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ExportFormat, TestScriptStatus


class TestStepRead(BaseModel):
    id: UUID
    step_number: int
    action: str
    description: str
    expected_outcome: str | None
    parameters: dict | None

    model_config = {"from_attributes": True}


class TestStepCreate(BaseModel):
    step_number: int = Field(ge=1)
    action: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    expected_outcome: str | None = None
    parameters: dict | None = None


class TestCaseRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    stop_on_failure: bool
    order_index: int
    steps: list[TestStepRead] = []

    model_config = {"from_attributes": True}


class TestCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    stop_on_failure: bool = False
    order_index: int = Field(default=0, ge=0)
    steps: list[TestStepCreate] = []


class TestScriptVersionRead(BaseModel):
    id: UUID
    test_script_id: UUID
    version: int
    script_content: str | None
    change_summary: str | None
    created_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TestScriptRead(BaseModel):
    id: UUID
    requirement_id: UUID | None
    system_id: UUID
    company_id: UUID
    title: str
    description: str | None
    version: int
    status: str
    export_format: str
    script_content: str | None
    ai_generated: bool
    ai_model_version: str | None
    approved_by: UUID | None
    approved_at: datetime | None
    business_domain: str | None
    tags: list | None
    created_by: UUID | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    cases: list[TestCaseRead] = []

    model_config = {"from_attributes": True}


class TestScriptCreate(BaseModel):
    requirement_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    export_format: ExportFormat = ExportFormat.PLAYWRIGHT
    business_domain: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = None
    cases: list[TestCaseCreate] = []


class TestScriptUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: TestScriptStatus | None = None
    export_format: ExportFormat | None = None
    script_content: str | None = None
    business_domain: str | None = None
    tags: list[str] | None = None
