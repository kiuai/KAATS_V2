from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ExportFormat


class EnterpriseRead(BaseModel):
    id: UUID
    name: str
    slug: str
    azure_ad_tenant_id: str | None
    is_active: bool
    settings: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EnterpriseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    azure_ad_tenant_id: str | None = Field(default=None, max_length=128)
    settings: dict | None = None


class EnterpriseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    azure_ad_tenant_id: str | None = None
    is_active: bool | None = None
    settings: dict | None = None


class CompanyRead(BaseModel):
    id: UUID
    enterprise_id: UUID
    name: str
    slug: str
    industry: str | None
    default_export_format: str
    is_active: bool
    is_deleted: bool
    settings: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyCreate(BaseModel):
    enterprise_id: UUID
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    industry: str | None = Field(default=None, max_length=255)
    default_export_format: ExportFormat = ExportFormat.PLAYWRIGHT
    settings: dict | None = None


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = None
    default_export_format: ExportFormat | None = None
    is_active: bool | None = None
    settings: dict | None = None
