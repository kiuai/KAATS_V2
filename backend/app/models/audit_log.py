"""Audit log — immutable append-only record of security-relevant actions."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class AuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_company_created", "company_id", "created_at"),
        Index("ix_audit_logs_actor", "actor_user_id"),
        Index("ix_audit_logs_event_type", "event_type"),
    )

    # Who did it (nullable = system / unauthenticated action)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Denormalised so log remains readable even after user deletion
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # Tenant scope (nullable for global-admin actions across all companies)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # What happened
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # What it affected (resource_type + resource_id form the "target")
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Before / after snapshot (kept small — only changed fields)
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Request context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max 45 chars
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Immutable timestamp — no updated_at
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default="GETUTCDATE()",
    )
