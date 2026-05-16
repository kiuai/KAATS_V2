"""Webhook endpoint and delivery models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class WebhookEndpoint(Base, UUIDPrimaryKeyMixin):
    """A company-owned HTTP endpoint that receives event payloads."""

    __tablename__ = "webhook_endpoints"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    # Comma-separated event types, e.g. "agent.completed,plan.updated"
    # NULL / empty = subscribe to all events
    event_types: Mapped[str | None] = mapped_column(String(1000))
    # HMAC-SHA256 signing secret (stored encrypted at rest via Azure Key Vault in prod;
    # plaintext here for simplicity — rotate via PATCH)
    secret: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    description: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.getutcdate(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.getutcdate(),
        onupdate=func.getutcdate(),
        nullable=False,
    )

    deliveries: Mapped[list[WebhookDelivery]] = relationship(
        "WebhookDelivery", back_populates="endpoint", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_webhook_endpoints_company", "company_id"),)


class WebhookDelivery(Base, UUIDPrimaryKeyMixin):
    """A single delivery attempt for a webhook event."""

    __tablename__ = "webhook_deliveries"

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UNIQUEIDENTIFIER(as_uuid=True),
        ForeignKey("companies.id", ondelete="NO ACTION"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(String(500))
    # "pending" | "success" | "failed"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.getutcdate(),
        nullable=False,
    )

    endpoint: Mapped[WebhookEndpoint] = relationship("WebhookEndpoint", back_populates="deliveries")

    __table_args__ = (Index("ix_webhook_deliveries_endpoint_created", "endpoint_id", "created_at"),)
