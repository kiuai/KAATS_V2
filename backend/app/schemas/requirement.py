from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RequirementRead(BaseModel):
    id: UUID
    system_id: UUID
    company_id: UUID
    title: str
    description: str
    status: str
    priority: int
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequirementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    priority: int = Field(default=2, ge=1, le=3)


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: str | None = Field(default=None, pattern=r"^(draft|approved|deprecated)$")
    priority: int | None = Field(default=None, ge=1, le=3)
