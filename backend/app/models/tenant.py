from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ExportFormat

if TYPE_CHECKING:
    from app.models.role import UserRole
    from app.models.system import System


class Enterprise(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enterprises"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    azure_ad_tenant_id: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    settings: Mapped[dict | None] = mapped_column(JSON)

    companies: Mapped[list[Company]] = relationship("Company", back_populates="enterprise")


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "companies"
    __table_args__ = (Index("ix_companies_enterprise", "enterprise_id"),)

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("enterprises.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(255))
    default_export_format: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ExportFormat.PLAYWRIGHT.value
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    settings: Mapped[dict | None] = mapped_column(JSON)

    enterprise: Mapped[Enterprise] = relationship("Enterprise", back_populates="companies")
    systems: Mapped[list[System]] = relationship("System", back_populates="company")
    user_roles: Mapped[list[UserRole]] = relationship("UserRole", back_populates="company")
