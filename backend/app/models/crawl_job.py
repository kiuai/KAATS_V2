from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CrawlJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks discrete crawl invocations. Linked to an AgentRun for the step trace."""

    __tablename__ = "crawl_jobs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    pages_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requirements_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
