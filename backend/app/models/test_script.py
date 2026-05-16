from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ExportFormat, TestScriptStatus

if TYPE_CHECKING:
    from app.models.requirement import Requirement
    from app.models.user import User


class TestScript(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "test_scripts"
    __table_args__ = (
        Index("ix_test_scripts_company_created", "company_id", "created_at"),
        Index("ix_test_scripts_system_status", "system_id", "status"),
    )

    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("requirements.id")
    )
    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("systems.id"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=TestScriptStatus.DRAFT.value
    )
    export_format: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ExportFormat.PLAYWRIGHT.value
    )
    script_content: Mapped[str | None] = mapped_column(Text)
    rendered_content: Mapped[str | None] = mapped_column(Text)
    ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    ai_model_version: Mapped[str | None] = mapped_column(String(100))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    business_domain: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[list | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )

    requirement: Mapped[Requirement | None] = relationship(
        "Requirement", back_populates="test_scripts"
    )
    versions: Mapped[list[TestScriptVersion]] = relationship(
        "TestScriptVersion", back_populates="script"
    )
    cases: Mapped[list[TestCase]] = relationship("TestCase", back_populates="script")
    approver: Mapped[User | None] = relationship("User", foreign_keys=[approved_by])
    creator: Mapped[User | None] = relationship("User", foreign_keys=[created_by])


class TestScriptVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_script_versions"

    test_script_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    script_content: Mapped[str | None] = mapped_column(Text)
    rendered_content: Mapped[str | None] = mapped_column(Text)
    change_summary: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )

    script: Mapped[TestScript] = relationship("TestScript", back_populates="versions")


class TestCase(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_cases"

    script_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    stop_on_failure: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    script: Mapped[TestScript] = relationship("TestScript", back_populates="cases")
    steps: Mapped[list[TestStep]] = relationship(
        "TestStep", back_populates="case", order_by="TestStep.step_number"
    )


class TestStep(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_steps"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_cases.id"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict | None] = mapped_column(JSON)

    case: Mapped[TestCase] = relationship("TestCase", back_populates="steps")
