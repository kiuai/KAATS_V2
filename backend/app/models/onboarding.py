from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.tenant import Company


class CompanyOnboarding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-company onboarding checklist.

    One row per company, tracking which first-run steps have been completed.
    The wizard in the frontend reads/writes this to drive the progress UI.
    """

    __tablename__ = "company_onboarding"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_company_onboarding_company"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )

    # Step 1 — company profile filled in
    has_profile: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Step 2 — at least one non-admin team member invited
    has_team_member: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Step 3 — first system / AUT created
    has_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # Step 4 — first agent run triggered
    has_agent_run: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])

    @property
    def is_complete(self) -> bool:
        return all(
            [self.has_profile, self.has_team_member, self.has_system, self.has_agent_run]
        )
