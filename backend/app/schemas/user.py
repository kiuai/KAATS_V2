from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRoleEnum


class UserRead(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    azure_oid: str | None
    is_active: bool
    is_global_admin: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=255)
    azure_oid: str | None = Field(default=None, max_length=128)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class UserRoleRead(BaseModel):
    id: UUID
    user_id: UUID
    enterprise_id: UUID | None
    company_id: UUID | None
    system_id: UUID | None
    role: str
    business_domain: str | None
    granted_by: UUID | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserRoleAssign(BaseModel):
    role: UserRoleEnum
    enterprise_id: UUID | None = None
    company_id: UUID | None = None
    system_id: UUID | None = None
    business_domain: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None
