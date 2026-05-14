"""Add invitation_tokens and company_onboarding tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-14 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── invitation_tokens ─────────────────────────────────────────────────────
    op.create_table(
        "invitation_tokens",
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
            "invited_by_id",
            mssql.UNIQUEIDENTIFIER(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=False), nullable=True),
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
    )
    op.create_index(
        "ix_invitation_tokens_company", "invitation_tokens", ["company_id"]
    )
    op.create_index(
        "ix_invitation_tokens_email", "invitation_tokens", ["email"]
    )
    op.create_index(
        "ix_invitation_tokens_token", "invitation_tokens", ["token"], unique=True
    )

    # ── company_onboarding ────────────────────────────────────────────────────
    op.create_table(
        "company_onboarding",
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
            "has_profile",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "has_team_member",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "has_system",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "has_agent_run",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
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
        sa.UniqueConstraint("company_id", name="uq_company_onboarding_company"),
    )


def downgrade() -> None:
    op.drop_table("company_onboarding")
    op.drop_index("ix_invitation_tokens_token", "invitation_tokens")
    op.drop_index("ix_invitation_tokens_email", "invitation_tokens")
    op.drop_index("ix_invitation_tokens_company", "invitation_tokens")
    op.drop_table("invitation_tokens")
