"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

Tables (in FK dependency order):
  1.  users
  2.  enterprises
  3.  companies
  4.  systems
  5.  user_roles
  6.  requirements
  7.  test_scripts
  8.  test_script_versions
  9.  test_cases
  10. test_steps
  11. test_cycles
  12. test_assignments
  13. test_executions
  14. test_step_results
  15. evidence_screenshots
  16. scheduled_jobs
  17. agent_runs
  18. agent_tool_calls
  19. company_token_usage
  20. test_results
  21. execution_runs
  22. execution_step_results
  23. crawl_jobs
  24. crawl_pages
  25. scheduled_job_runs
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("azure_oid", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_global_admin", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("azure_oid"),
    )

    # ── 2. enterprises ────────────────────────────────────────────────────────
    op.create_table(
        "enterprises",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("azure_ad_tenant_id", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # ── 3. companies ─────────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("enterprise_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("default_export_format", sa.String(50), nullable=False, server_default="playwright"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_enterprise", "companies", ["enterprise_id"])

    # ── 4. systems ────────────────────────────────────────────────────────────
    op.create_table(
        "systems",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2048), nullable=True),
        sa.Column("system_type", sa.String(50), nullable=False, server_default="web_application"),
        sa.Column("base_url", sa.String(2048), nullable=True),
        sa.Column("system_manager_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("industry_domain", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["system_manager_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_systems_company_id", "systems", ["company_id"])
    op.create_index("ix_systems_company_created", "systems", ["company_id", "created_at"])

    # ── 5. user_roles ─────────────────────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("user_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("enterprise_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("system_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("business_domain", sa.String(255), nullable=True),
        sa.Column("granted_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_roles_user", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_company", "user_roles", ["company_id"])

    # ── 6. requirements ───────────────────────────────────────────────────────
    op.create_table(
        "requirements",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("system_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("source_reference", sa.String(500), nullable=True),
        sa.Column("business_domain", sa.String(255), nullable=True),
        sa.Column("priority", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requirements_system_id", "requirements", ["system_id"])
    op.create_index("ix_requirements_company_id", "requirements", ["company_id"])
    op.create_index("ix_requirements_company_created", "requirements", ["company_id", "created_at"])
    op.create_index("ix_requirements_system_status", "requirements", ["system_id", "status"])

    # ── 7. test_scripts ───────────────────────────────────────────────────────
    op.create_table(
        "test_scripts",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("requirement_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("system_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("export_format", sa.String(50), nullable=False, server_default="playwright"),
        sa.Column("script_content", sa.Text(), nullable=True),
        sa.Column("rendered_content", sa.Text(), nullable=True),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("ai_model_version", sa.String(100), nullable=True),
        sa.Column("approved_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("business_domain", sa.String(255), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"]),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_scripts_system_id", "test_scripts", ["system_id"])
    op.create_index("ix_test_scripts_company_id", "test_scripts", ["company_id"])
    op.create_index("ix_test_scripts_company_created", "test_scripts", ["company_id", "created_at"])
    op.create_index("ix_test_scripts_system_status", "test_scripts", ["system_id", "status"])

    # ── 8. test_script_versions ───────────────────────────────────────────────
    op.create_table(
        "test_script_versions",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("test_script_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("script_content", sa.Text(), nullable=True),
        sa.Column("rendered_content", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.String(1000), nullable=True),
        sa.Column("created_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["test_script_id"], ["test_scripts.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_script_versions_script", "test_script_versions", ["test_script_id"])

    # ── 9. test_cases ─────────────────────────────────────────────────────────
    op.create_table(
        "test_cases",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("script_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stop_on_failure", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["script_id"], ["test_scripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_cases_script", "test_cases", ["script_id"])

    # ── 10. test_steps ────────────────────────────────────────────────────────
    op.create_table(
        "test_steps",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("case_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["test_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_steps_case", "test_steps", ["case_id"])

    # ── 11. test_cycles ───────────────────────────────────────────────────────
    op.create_table(
        "test_cycles",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("system_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="planned"),
        sa.Column("planned_start", sa.DateTime(), nullable=True),
        sa.Column("planned_end", sa.DateTime(), nullable=True),
        sa.Column("actual_start", sa.DateTime(), nullable=True),
        sa.Column("actual_end", sa.DateTime(), nullable=True),
        sa.Column("lead_user_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("created_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["lead_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_cycles_system_id", "test_cycles", ["system_id"])
    op.create_index("ix_test_cycles_company_id", "test_cycles", ["company_id"])
    op.create_index("ix_test_cycles_company_created", "test_cycles", ["company_id", "created_at"])

    # ── 12. test_assignments ──────────────────────────────────────────────────
    op.create_table(
        "test_assignments",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("test_cycle_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("test_script_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("assigned_to", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("assigned_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["test_cycle_id"], ["test_cycles.id"]),
        sa.ForeignKeyConstraint(["test_script_id"], ["test_scripts.id"]),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_assignments_cycle", "test_assignments", ["test_cycle_id"])

    # ── 13. test_executions (legacy) ──────────────────────────────────────────
    op.create_table(
        "test_executions",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("script_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("system_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("triggered_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("passed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["script_id"], ["test_scripts.id"]),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_executions_script", "test_executions", ["script_id"])
    op.create_index("ix_test_executions_system", "test_executions", ["system_id"])
    op.create_index("ix_test_executions_company", "test_executions", ["company_id"])
    op.create_index("ix_test_executions_company_created", "test_executions", ["company_id"])

    # ── 14. test_step_results (legacy) ────────────────────────────────────────
    op.create_table(
        "test_step_results",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("execution_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("step_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("actual_outcome", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["test_executions.id"]),
        sa.ForeignKeyConstraint(["step_id"], ["test_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_step_results_execution", "test_step_results", ["execution_id"])

    # ── 15. evidence_screenshots ──────────────────────────────────────────────
    op.create_table(
        "evidence_screenshots",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("execution_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("step_result_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("blob_path", sa.String(2048), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["execution_id"], ["test_executions.id"]),
        sa.ForeignKeyConstraint(["step_result_id"], ["test_step_results.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_execution_id", "evidence_screenshots", ["execution_id"])
    op.create_index("ix_evidence_company_id", "evidence_screenshots", ["company_id"])
    op.create_index("ix_evidence_execution_step", "evidence_screenshots", ["execution_id", "step_number"])

    # ── 16. scheduled_jobs ────────────────────────────────────────────────────
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("system_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("created_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("schedule_type", sa.String(50), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column("run_at", sa.DateTime(), nullable=True),
        sa.Column("job_config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("max_failures", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_status", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_jobs_company_id", "scheduled_jobs", ["company_id"])
    op.create_index("ix_scheduled_jobs_system_id", "scheduled_jobs", ["system_id"])

    # ── 17. agent_runs ────────────────────────────────────────────────────────
    op.create_table(
        "agent_runs",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("system_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("trigger_type", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("triggered_by_user_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("scheduled_job_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("service_bus_message_id", sa.String(255), nullable=True),
        sa.Column("input_config", sa.JSON(), nullable=True),
        sa.Column("output_summary", sa.JSON(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["scheduled_job_id"], ["scheduled_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_company_id", "agent_runs", ["company_id"])
    op.create_index("ix_agent_runs_system_id", "agent_runs", ["system_id"])

    # ── 18. agent_tool_calls ──────────────────────────────────────────────────
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("agent_run_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("tool_input", sa.JSON(), nullable=True),
        sa.Column("tool_output", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("called_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tool_calls_run", "agent_tool_calls", ["agent_run_id"])

    # ── 19. company_token_usage ───────────────────────────────────────────────
    op.create_table(
        "company_token_usage",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("usage_date", sa.DateTime(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_token_usage_company", "company_token_usage", ["company_id"])

    # ── 20. test_results ──────────────────────────────────────────────────────
    op.create_table(
        "test_results",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("assignment_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("test_script_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("executed_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("execution_agent_run_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("defect_reference", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["assignment_id"], ["test_assignments.id"]),
        sa.ForeignKeyConstraint(["test_script_id"], ["test_scripts.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["executed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["execution_agent_run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_results_assignment", "test_results", ["assignment_id"])
    op.create_index("ix_test_results_company_id", "test_results", ["company_id"])
    op.create_index("ix_test_results_company_created", "test_results", ["company_id", "created_at"])

    # ── 21. execution_runs ────────────────────────────────────────────────────
    op.create_table(
        "execution_runs",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("test_result_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("agent_run_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("test_script_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("total_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_pdf_blob_url", sa.String(2048), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["test_result_id"], ["test_results.id"]),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["test_script_id"], ["test_scripts.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_runs_agent_run", "execution_runs", ["agent_run_id"])
    op.create_index("ix_execution_runs_company_id", "execution_runs", ["company_id"])
    op.create_index("ix_execution_runs_company_created", "execution_runs", ["company_id", "created_at"])

    # ── 22. execution_step_results ────────────────────────────────────────────
    op.create_table(
        "execution_step_results",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("execution_run_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("step_description", sa.Text(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("locator", sa.String(2048), nullable=True),
        sa.Column("input_value", sa.String(2048), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=False),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("screenshot_blob_url", sa.String(2048), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["execution_run_id"], ["execution_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_step_results_run", "execution_step_results", ["execution_run_id"])

    # ── 23. crawl_jobs ────────────────────────────────────────────────────────
    op.create_table(
        "crawl_jobs",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("system_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("company_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("crawler_type", sa.String(50), nullable=False, server_default="web"),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("crawl_config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("triggered_by", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("scheduled_job_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("agent_run_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("pages_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requirements_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["system_id"], ["systems.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["scheduled_job_id"], ["scheduled_jobs.id"]),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crawl_jobs_system_id", "crawl_jobs", ["system_id"])
    op.create_index("ix_crawl_jobs_company_id", "crawl_jobs", ["company_id"])
    op.create_index("ix_crawl_jobs_company_created", "crawl_jobs", ["company_id", "created_at"])
    op.create_index("ix_crawl_jobs_system_status", "crawl_jobs", ["system_id", "status"])

    # ── 24. crawl_pages ───────────────────────────────────────────────────────
    op.create_table(
        "crawl_pages",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("crawl_job_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("page_type", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("ui_elements", sa.JSON(), nullable=True),
        sa.Column("interactions", sa.JSON(), nullable=True),
        sa.Column("screenshot_blob_url", sa.String(2048), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("requirement_ids", sa.JSON(), nullable=True),
        sa.Column("crawled_at", sa.DateTime(), nullable=False, server_default=sa.text("GETUTCDATE()")),
        sa.ForeignKeyConstraint(["crawl_job_id"], ["crawl_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crawl_pages_job", "crawl_pages", ["crawl_job_id"])

    # ── 25. scheduled_job_runs ────────────────────────────────────────────────
    op.create_table(
        "scheduled_job_runs",
        sa.Column("id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False, server_default=sa.text("NEWSEQUENTIALID()")),
        sa.Column("job_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", mssql.UNIQUEIDENTIFIER(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="triggered"),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["scheduled_jobs.id"]),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_job_runs_job", "scheduled_job_runs", ["job_id"])


def downgrade() -> None:
    op.drop_table("scheduled_job_runs")
    op.drop_table("crawl_pages")
    op.drop_table("crawl_jobs")
    op.drop_table("execution_step_results")
    op.drop_table("execution_runs")
    op.drop_table("test_results")
    op.drop_table("company_token_usage")
    op.drop_table("agent_tool_calls")
    op.drop_table("agent_runs")
    op.drop_table("scheduled_jobs")
    op.drop_table("evidence_screenshots")
    op.drop_table("test_step_results")
    op.drop_table("test_executions")
    op.drop_table("test_assignments")
    op.drop_table("test_cycles")
    op.drop_table("test_steps")
    op.drop_table("test_cases")
    op.drop_table("test_script_versions")
    op.drop_table("test_scripts")
    op.drop_table("requirements")
    op.drop_table("user_roles")
    op.drop_table("systems")
    op.drop_table("companies")
    op.drop_table("enterprises")
    op.drop_table("users")
