from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_runs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    system_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("systems.id"), index=True
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id")
    )
    scheduled_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("scheduled_jobs.id")
    )
    service_bus_message_id: Mapped[str | None] = mapped_column(String(255))
    input_config: Mapped[dict | None] = mapped_column(JSON)
    output_summary: Mapped[dict | None] = mapped_column(JSON)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    tool_calls: Mapped[list["AgentToolCall"]] = relationship(
        "AgentToolCall", back_populates="agent_run"
    )


class AgentToolCall(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "agent_tool_calls"

    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_input: Mapped[dict | None] = mapped_column(JSON)
    tool_output: Mapped[dict | None] = mapped_column(JSON)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="tool_calls")


class CompanyTokenUsage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "company_token_usage"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    usage_date: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
