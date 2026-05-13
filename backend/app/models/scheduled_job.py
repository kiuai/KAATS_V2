from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ScheduledJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scheduled_jobs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    runs: Mapped[list["ScheduledJobRun"]] = relationship(
        "ScheduledJobRun", back_populates="job"
    )


class ScheduledJobRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "scheduled_job_runs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("scheduled_jobs.id"), nullable=False, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="enqueued")
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    failure_reason: Mapped[str | None] = mapped_column(Text)

    job: Mapped["ScheduledJob"] = relationship("ScheduledJob", back_populates="runs")
