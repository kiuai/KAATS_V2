from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RequirementPriority, RequirementSourceType, RequirementStatus

if TYPE_CHECKING:
    from app.models.system import System
    from app.models.test_script import TestScript
    from app.models.user import User


class Requirement(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "requirements"
    __table_args__ = (
        Index("ix_requirements_company_created", "company_id", "created_at"),
        Index("ix_requirements_system_status", "system_id", "status"),
    )

    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("systems.id"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=RequirementSourceType.MANUAL.value
    )
    source_reference: Mapped[str | None] = mapped_column(String(500))
    business_domain: Mapped[str | None] = mapped_column(String(255))
    priority: Mapped[str] = mapped_column(
        String(50), nullable=False, default=RequirementPriority.MEDIUM.value
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=RequirementStatus.DRAFT.value
    )
    tags: Mapped[list | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )

    system: Mapped[System] = relationship("System", back_populates="requirements")
    test_scripts: Mapped[list[TestScript]] = relationship(
        "TestScript", back_populates="requirement"
    )
    created_by_user: Mapped[User | None] = relationship("User", foreign_keys=[created_by])
