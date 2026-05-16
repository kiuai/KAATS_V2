from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EvidenceScreenshotRead(BaseModel):
    id: UUID
    execution_id: UUID
    step_result_id: UUID | None
    company_id: UUID
    blob_path: str
    sha256: str
    step_number: int
    captured_at: datetime

    model_config = {"from_attributes": True}


class EvidenceVerifyResult(BaseModel):
    valid: bool
    failed_steps: list[int] = []
    checked_at: datetime


class ExecutionStepResultRead(BaseModel):
    id: UUID
    execution_run_id: UUID
    step_number: int
    step_description: str
    action: str
    locator: str | None
    input_value: str | None
    expected_result: str
    actual_result: str | None
    outcome: str
    screenshot_blob_url: str | None
    error_message: str | None
    duration_ms: int
    executed_at: datetime

    model_config = {"from_attributes": True}


class ExecutionRunRead(BaseModel):
    id: UUID
    test_result_id: UUID | None
    agent_run_id: UUID
    test_script_id: UUID
    company_id: UUID
    status: str
    total_steps: int
    passed_steps: int
    failed_steps: int
    evidence_pdf_blob_url: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    step_results: list[ExecutionStepResultRead] = []

    model_config = {"from_attributes": True}
