"""Add company_plans table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-14 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_plans",
        sa.Column(
            "id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            nullable=False,
            server_default=sa.text("NEWSEQUENTIALID()"),
        ),
        sa.Column(
            "company_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "plan_tier",
            sa.String(50),
            nullable=False,
            server_default="free",
        ),
        sa.Column("monthly_token_limit", sa.Integer(), nullable=True),
        sa.Column("monthly_agent_run_limit", sa.Integer(), nullable=True),
        sa.Column("max_systems", sa.Integer(), nullable=True),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column("max_concurrent_agents", sa.Integer(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("GETUTCDATE()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("GETUTCDATE()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_company_plans_company"),
    )


def downgrade() -> None:
    op.drop_table("company_plans")
