from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import RequirementPriority, RequirementSourceType, RequirementStatus


class RequirementRead(BaseModel):
    id: UUID
    system_id: UUID
    company_id: UUID
    title: str
    description: str
    source_type: str
    source_reference: str | None
    business_domain: str | None
    priority: str
    status: str
    tags: list | None
    created_by: UUID | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequirementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1)
    source_type: RequirementSourceType = RequirementSourceType.MANUAL
    source_reference: str | None = Field(default=None, max_length=500)
    business_domain: str | None = Field(default=None, max_length=255)
    priority: RequirementPriority = RequirementPriority.MEDIUM
    tags: list[str] | None = None


class RequirementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    source_reference: str | None = None
    business_domain: str | None = None
    priority: RequirementPriority | None = None
    status: RequirementStatus | None = None
    tags: list[str] | None = None
