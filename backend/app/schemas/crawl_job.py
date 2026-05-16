from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import CrawlerType


class CrawlPageRead(BaseModel):
    id: UUID
    crawl_job_id: UUID
    url: str
    title: str | None
    page_type: str
    ui_elements: list | None
    interactions: list | None
    screenshot_blob_url: str | None
    ai_summary: str | None
    requirement_ids: list | None
    crawled_at: datetime

    model_config = {"from_attributes": True}


class CrawlJobRead(BaseModel):
    id: UUID
    system_id: UUID
    company_id: UUID
    crawler_type: str
    target_url: str
    crawl_config: dict | None
    status: str
    triggered_by: str
    scheduled_job_id: UUID | None
    agent_run_id: UUID | None
    pages_discovered: int
    requirements_generated: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CrawlJobCreate(BaseModel):
    system_id: UUID
    crawler_type: CrawlerType = CrawlerType.WEB
    target_url: str = Field(min_length=1, max_length=2048)
    crawl_config: dict | None = None


class CrawlJobWithPages(CrawlJobRead):
    pages: list[CrawlPageRead] = []
