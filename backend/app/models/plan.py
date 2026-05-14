"""CompanyPlan — per-company quota and plan-tier configuration.

One row per company.  Absent row → Free tier defaults (see UsageService).
Limits of None mean unlimited (Enterprise tier).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Company


class CompanyPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Quota configuration for a single company tenant."""

    __tablename__ = "company_plans"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_plans_company"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )

    # ── Plan tier ─────────────────────────────────────────────────────────────
    plan_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, default="free", server_default="free"
    )

    # ── Monthly usage caps (None = unlimited) ─────────────────────────────────
    monthly_token_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_agent_run_limit: Mapped[int | None] = mapped_column(Integer)

    # ── Structural caps ───────────────────────────────────────────────────────
    max_systems: Mapped[int | None] = mapped_column(Integer)
    max_users: Mapped[int | None] = mapped_column(Integer)
    max_concurrent_agents: Mapped[int | None] = mapped_column(Integer)

    # ── Audit ─────────────────────────────────────────────────────────────────
    override_reason: Mapped[str | None] = mapped_column(Text)

    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])
