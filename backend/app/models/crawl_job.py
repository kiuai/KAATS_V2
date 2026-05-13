from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CrawlJobStatus, CrawlerType, CrawlTriggerType, PageType

if TYPE_CHECKING:
    from app.models.user import User


class CrawlJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "crawl_jobs"
    __table_args__ = (
        Index("ix_crawl_jobs_company_created", "company_id", "created_at"),
        Index("ix_crawl_jobs_system_status", "system_id", "status"),
    )

    system_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("systems.id"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    crawler_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=CrawlerType.WEB.value
    )
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    crawl_config: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=CrawlJobStatus.PENDING.value
    )
    triggered_by: Mapped[str] = mapped_column(
        String(50), nullable=False, default=CrawlTriggerType.MANUAL.value
    )
    scheduled_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("scheduled_jobs.id")
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("agent_runs.id")
    )
    pages_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requirements_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )

    pages: Mapped[list["CrawlPage"]] = relationship("CrawlPage", back_populates="crawl_job")


class CrawlPage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "crawl_pages"

    crawl_job_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("crawl_jobs.id"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    page_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=PageType.UNKNOWN.value
    )
    ui_elements: Mapped[list | None] = mapped_column(JSON)
    interactions: Mapped[list | None] = mapped_column(JSON)
    screenshot_blob_url: Mapped[str | None] = mapped_column(String(2048))
    ai_summary: Mapped[str | None] = mapped_column(Text)
    requirement_ids: Mapped[list | None] = mapped_column(JSON)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default="GETUTCDATE()", nullable=False
    )

    crawl_job: Mapped["CrawlJob"] = relationship("CrawlJob", back_populates="pages")
