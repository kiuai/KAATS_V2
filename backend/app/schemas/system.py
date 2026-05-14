from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import SystemType


class SystemRead(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: str | None
    system_type: str
    base_url: str | None
    system_manager_id: UUID | None
    industry_domain: str | None
    is_active: bool
    is_deleted: bool
    settings: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    system_type: SystemType = SystemType.WEB_APPLICATION
    base_url: str | None = Field(default=None, max_length=2048)
    system_manager_id: UUID | None = None
    industry_domain: str | None = Field(default=None, max_length=255)
    settings: dict | None = None


class SystemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    system_type: SystemType | None = None
    base_url: str | None = None
    system_manager_id: UUID | None = None
    industry_domain: str | None = None
    is_active: bool | None = None
    settings: dict | None = None


class SystemStats(BaseModel):
    requirement_count: int
    active_requirement_count: int
    script_count: int
    approved_script_count: int
    coverage_pct: float
    last_crawl_at: datetime | None
    last_execution_at: datetime | None


class SystemDetailRead(SystemRead):
    stats: SystemStats | None = None


class AssignManagerBody(BaseModel):
    user_id: UUID
