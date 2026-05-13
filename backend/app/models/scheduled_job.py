from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun


class ScheduledJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scheduled_jobs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    system_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("systems.id"), index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    job_config: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    max_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_run_status: Mapped[str | None] = mapped_column(String(50))

    runs: Mapped[list["ScheduledJobRun"]] = relationship(
        "ScheduledJobRun", back_populates="job"
    )


class ScheduledJobRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "scheduled_job_runs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("scheduled_jobs.id"), nullable=False, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("agent_runs.id")
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="triggered")
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    failure_reason: Mapped[str | None] = mapped_column(Text)

    job: Mapped["ScheduledJob"] = relationship("ScheduledJob", back_populates="runs")
    agent_run: Mapped["AgentRun | None"] = relationship("AgentRun")
