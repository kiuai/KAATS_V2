from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import ExecutionStatus, StepOutcome

if TYPE_CHECKING:
    from app.models.test_result import TestResult
    from app.models.agent_run import AgentRun
    from app.models.test_script import TestScript


class ExecutionRun(Base, UUIDPrimaryKeyMixin):
    """AI-agent execution of a test script — generates per-step evidence."""
    __tablename__ = "execution_runs"
    __table_args__ = (
        Index("ix_execution_runs_company_created", "company_id", "created_at"),
    )

    test_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_results.id")
    )
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    test_script_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ExecutionStatus.RUNNING.value
    )
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_pdf_blob_url: Mapped[str | None] = mapped_column(String(2048))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )

    step_results: Mapped[list["ExecutionStepResult"]] = relationship(
        "ExecutionStepResult", back_populates="execution_run"
    )


class ExecutionStepResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "execution_step_results"

    execution_run_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True),
        ForeignKey("execution_runs.id"),
        nullable=False,
        index=True,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_description: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    locator: Mapped[str | None] = mapped_column(String(2048))
    input_value: Mapped[str | None] = mapped_column(String(2048))
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    actual_result: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    screenshot_blob_url: Mapped[str | None] = mapped_column(String(2048))
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )

    execution_run: Mapped["ExecutionRun"] = relationship("ExecutionRun", back_populates="step_results")
