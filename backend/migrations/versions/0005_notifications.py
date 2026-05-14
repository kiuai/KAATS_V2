"""Add notifications table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            server_default=sa.text("NEWSEQUENTIALID()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", sa.String(20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("read_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.text("GETUTCDATE()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_read",
        "notifications",
        ["user_id", "is_read"],
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_table("notifications")
