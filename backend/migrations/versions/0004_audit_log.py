"""audit_log table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            nullable=False,
            server_default=sa.text("NEWSEQUENTIALID()"),
        ),
        sa.Column(
            "actor_user_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(320), nullable=True),
        sa.Column(
            "company_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("changes", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("GETUTCDATE()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_company_created", "audit_logs", ["company_id", "created_at"])
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor", table_name="audit_logs")
    op.drop_index("ix_audit_logs_company_created", table_name="audit_logs")
    op.drop_table("audit_logs")
