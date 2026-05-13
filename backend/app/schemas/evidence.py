from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EvidenceScreenshotRead(BaseModel):
    id: UUID
    execution_id: UUID
    step_result_id: UUID | None
    blob_path: str
    sas_url: str | None
    sha256: str
    step_number: int
    captured_at: datetime

    model_config = {"from_attributes": True}


class EvidenceVerifyResult(BaseModel):
    valid: bool
    failed_steps: list[int] = []
    checked_at: datetime
