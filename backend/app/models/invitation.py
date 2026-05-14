from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import InvitationStatus, UserRoleEnum

if TYPE_CHECKING:
    from app.models.tenant import Company
    from app.models.user import User


def _default_token() -> str:
    return secrets.token_urlsafe(32)


class InvitationToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Token-based email invitation for new users.

    Flow:
      1. company_admin POSTs /api/v1/onboarding/invitations → row created, email sent.
      2. Recipient opens /accept-invite?token=<token> → GET validates token.
      3. Recipient completes sign-up → POST /accept consumes the token.
    """

    __tablename__ = "invitation_tokens"
    __table_args__ = (
        Index("ix_invitation_tokens_company", "company_id"),
        Index("ix_invitation_tokens_email", "email"),
        Index("ix_invitation_tokens_token", "token", unique=True),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default=UserRoleEnum.QA.value
    )
    token: Mapped[str] = mapped_column(
        String(128), nullable=False, default=_default_token
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=InvitationStatus.PENDING.value,
        server_default="pending",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))

    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])
    invited_by: Mapped["User | None"] = relationship("User", foreign_keys=[invited_by_id])
