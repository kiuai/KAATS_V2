from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class AgentRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "agent_runs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    system_id: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    execution_id: Mapped[uuid.UUID | None] = mapped_column(UNIQUEIDENTIFIER(as_uuid=True))
    cosmos_doc_id: Mapped[str | None] = mapped_column(String(255))
    evidence_pdf_path: Mapped[str | None] = mapped_column(String(2048))
    evidence_integrity_hash: Mapped[str | None] = mapped_column(String(64))


class CompanyTokenUsage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "company_token_usage"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), nullable=False, index=True
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    usage_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
