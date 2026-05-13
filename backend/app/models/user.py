from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Company


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    entra_oid: Mapped[str | None] = mapped_column(String(128), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    company_roles: Mapped[list["UserCompanyRole"]] = relationship(
        "UserCompanyRole", back_populates="user"
    )


class UserCompanyRole(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "user_company_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.getutcdate(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="company_roles")
    company: Mapped["Company"] = relationship("Company", back_populates="user_roles")
