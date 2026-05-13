from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRoleEnum

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.tenant import Company
    from app.models.system import System


class UserRole(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Multi-level role assignment.
    Scope is determined by which FK is non-null:
      - enterprise_id only     → ENTERPRISE_ADMIN
      - company_id only        → COMPANY_ADMIN / QA / etc.
      - company_id + system_id → SYSTEM_MANAGER scoped to a specific system
    """
    __tablename__ = "user_roles"
    __table_args__ = (
        Index("ix_user_roles_user", "user_id"),
        Index("ix_user_roles_company", "company_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    enterprise_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("enterprises.id")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id")
    )
    system_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("systems.id")
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    business_domain: Mapped[str | None] = mapped_column(String(255))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    user: Mapped["User"] = relationship("User", back_populates="roles", foreign_keys=[user_id])
    company: Mapped["Company | None"] = relationship("Company", back_populates="user_roles")
