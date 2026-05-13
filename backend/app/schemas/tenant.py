from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EnterpriseRead(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyRead(BaseModel):
    id: UUID
    enterprise_id: UUID
    name: str
    slug: str
    business_domain: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyCreate(BaseModel):
    enterprise_id: UUID
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    business_domain: str | None = Field(default=None, max_length=500)


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    business_domain: str | None = None
    is_active: bool | None = None
