from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.test_cycle import TestAssignment
    from app.models.user import User


class TestResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_results"
    __table_args__ = (Index("ix_test_results_company_created", "company_id", "created_at"),)

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True),
        ForeignKey("test_assignments.id"),
        nullable=False,
        index=True,
    )
    test_script_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    executed_by: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    execution_agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("agent_runs.id")
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_result: Mapped[str | None] = mapped_column(Text)
    defect_reference: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )

    assignment: Mapped[TestAssignment] = relationship("TestAssignment", back_populates="results")
    executor: Mapped[User] = relationship("User")


class EvidenceScreenshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evidence_screenshots"
    __table_args__ = (Index("ix_evidence_execution_step", "execution_id", "step_number"),)

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_executions.id"), nullable=False, index=True
    )
    step_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_step_results.id")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    blob_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class TestStepResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_step_results"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_executions.id"), nullable=False, index=True
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_steps.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_outcome: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    screenshot: Mapped[EvidenceScreenshot | None] = relationship(
        "EvidenceScreenshot",
        primaryjoin="TestStepResult.id == EvidenceScreenshot.step_result_id",
        foreign_keys="[EvidenceScreenshot.step_result_id]",
        uselist=False,
    )
