from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.requirement import Requirement
    from app.models.tenant import Company


class System(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "systems"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    system_type: Mapped[str] = mapped_column(String(100), nullable=False, default="web_app")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    crawl_config: Mapped[str | None] = mapped_column(Text)
    auth_config: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    company: Mapped["Company"] = relationship("Company", back_populates="systems")
    requirements: Mapped[list["Requirement"]] = relationship(
        "Requirement", back_populates="system"
    )
