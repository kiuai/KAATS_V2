from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field


class SystemRead(BaseModel):
    id: UUID
    company_id: UUID
    owner_id: UUID
    name: str
    base_url: str
    system_type: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: AnyHttpUrl
    system_type: str = Field(default="web_app", pattern=r"^(web_app|api|mobile_web|desktop_web|other)$")
    crawl_config: dict | None = None
    auth_config: dict | None = None


class SystemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: AnyHttpUrl | None = None
    system_type: str | None = None
    status: str | None = None
    crawl_config: dict | None = None
    auth_config: dict | None = None
