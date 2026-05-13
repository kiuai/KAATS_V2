from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.system import System
    from app.models.user import UserCompanyRole


class Enterprise(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enterprises"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    companies: Mapped[list["Company"]] = relationship("Company", back_populates="enterprise")


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "companies"

    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("enterprises.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    business_domain: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    enterprise: Mapped["Enterprise"] = relationship("Enterprise", back_populates="companies")
    systems: Mapped[list["System"]] = relationship("System", back_populates="company")
    user_roles: Mapped[list["UserCompanyRole"]] = relationship(
        "UserCompanyRole", back_populates="company"
    )
