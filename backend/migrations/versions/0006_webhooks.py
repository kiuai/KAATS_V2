"""Add webhook_endpoints and webhook_deliveries tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column(
            "id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            server_default=sa.text("NEWSEQUENTIALID()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("event_types", sa.String(1000), nullable=True),
        sa.Column("secret", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "created_by_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.text("GETUTCDATE()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.text("GETUTCDATE()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_endpoints_company", "webhook_endpoints", ["company_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            server_default=sa.text("NEWSEQUENTIALID()"),
            nullable=False,
        ),
        sa.Column(
            "endpoint_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="NO ACTION"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("delivered_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.text("GETUTCDATE()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webhook_deliveries_endpoint_created",
        "webhook_deliveries",
        ["endpoint_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_endpoint_created", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhook_endpoints_company", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
