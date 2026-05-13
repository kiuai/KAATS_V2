from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TestAssignmentStatus, TestCycleStatus

if TYPE_CHECKING:
    from app.models.test_script import TestScript
    from app.models.user import User


class TestCycle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "test_cycles"
    __table_args__ = (
        Index("ix_test_cycles_company_created", "company_id", "created_at"),
    )

    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("systems.id"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=TestCycleStatus.PLANNED.value
    )
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    lead_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )

    assignments: Mapped[list["TestAssignment"]] = relationship("TestAssignment", back_populates="cycle")
    lead_user: Mapped["User | None"] = relationship("User", foreign_keys=[lead_user_id])
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])


class TestAssignment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "test_assignments"

    test_cycle_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_cycles.id"), nullable=False, index=True
    )
    test_script_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=TestAssignmentStatus.PENDING.value
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )

    cycle: Mapped["TestCycle"] = relationship("TestCycle", back_populates="assignments")
    test_script: Mapped["TestScript"] = relationship("TestScript")
    assignee: Mapped["User"] = relationship("User", foreign_keys=[assigned_to])
    assigner: Mapped["User"] = relationship("User", foreign_keys=[assigned_by])
    results: Mapped[list["TestResult"]] = relationship("TestResult", back_populates="assignment")


# Keep for backward compat with existing router/service until full refactor
class TestExecution(Base, UUIDPrimaryKeyMixin):
    """Legacy model — superseded by TestCycle/TestAssignment/ExecutionRun."""
    __tablename__ = "test_executions"
    __table_args__ = (
        Index("ix_test_executions_company_id", "company_id"),
    )

    script_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False, index=True
    )
    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("systems.id"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    passed_count: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column()

    script: Mapped["TestScript"] = relationship("TestScript")


# Import TestResult here for the FK relationship on TestAssignment
from app.models.test_result import TestResult  # noqa: E402
