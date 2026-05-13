from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SystemType

if TYPE_CHECKING:
    from app.models.tenant import Company
    from app.models.requirement import Requirement
    from app.models.user import User


class System(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "systems"
    __table_args__ = (
        Index("ix_systems_company_created", "company_id", "created_at"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048))
    system_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=SystemType.WEB_APPLICATION.value
    )
    base_url: Mapped[str | None] = mapped_column(String(2048))
    system_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )
    industry_domain: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    settings: Mapped[dict | None] = mapped_column(JSON)

    company: Mapped["Company"] = relationship("Company", back_populates="systems")
    requirements: Mapped[list["Requirement"]] = relationship("Requirement", back_populates="system")
    system_manager: Mapped["User | None"] = relationship("User", foreign_keys=[system_manager_id])
