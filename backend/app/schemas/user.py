from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class RoleAssign(BaseModel):
    role: str = Field(
        pattern=r"^(platform_admin|enterprise_admin|company_admin|system_manager|qa_engineer|viewer)$"
    )
