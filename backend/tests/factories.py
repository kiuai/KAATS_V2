"""
Test data factories.

Plain Python — no external deps. Returns SQLAlchemy model instances with
minimal required fields pre-populated. Use these in fixtures to seed the DB
or to construct in-memory objects for unit tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


# ── Lazy imports so unit tests that don't need models can still import factories ──

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC matches SQL Server


# ─────────────────────────────────────────────────────────────────────────────
# Tenant factories
# ─────────────────────────────────────────────────────────────────────────────

def create_enterprise(
    *,
    name: str = "Test Enterprise",
    slug: str | None = None,
    is_active: bool = True,
) -> dict:
    """Minimal enterprise record dict (pass as **kwargs to Enterprise(...))."""
    eid = uuid.uuid4()
    return {
        "id": eid,
        "name": name,
        "slug": slug or f"enterprise-{eid.hex[:8]}",
        "is_active": is_active,
        "settings": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


def create_company(
    enterprise_id: uuid.UUID,
    *,
    name: str = "Test Company",
    slug: str | None = None,
    is_active: bool = True,
) -> dict:
    """Minimal company record dict."""
    cid = uuid.uuid4()
    return {
        "id": cid,
        "enterprise_id": enterprise_id,
        "name": name,
        "slug": slug or f"company-{cid.hex[:8]}",
        "industry": None,
        "default_export_format": "playwright",
        "is_active": is_active,
        "is_deleted": False,
        "deleted_at": None,
        "settings": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# User factories
# ─────────────────────────────────────────────────────────────────────────────

def create_user(
    *,
    email: str | None = None,
    display_name: str = "Test User",
    is_global_admin: bool = False,
    is_active: bool = True,
) -> dict:
    """Minimal user record dict."""
    uid = uuid.uuid4()
    return {
        "id": uid,
        "email": email or f"user-{uid.hex[:8]}@test.com",
        "display_name": display_name,
        "azure_oid": str(uuid.uuid4()),
        "is_active": is_active,
        "is_global_admin": is_global_admin,
        "last_login_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


def create_user_role(
    user_id: uuid.UUID,
    company_id: uuid.UUID | None,
    *,
    role: str = "qa",
    enterprise_id: uuid.UUID | None = None,
    system_id: uuid.UUID | None = None,
    business_domain: str | None = None,
) -> dict:
    """Minimal user role record dict."""
    return {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "enterprise_id": enterprise_id,
        "company_id": company_id,
        "system_id": system_id,
        "role": role,
        "business_domain": business_domain,
        "granted_by": None,
        "expires_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# System factories
# ─────────────────────────────────────────────────────────────────────────────

def create_system(
    company_id: uuid.UUID,
    manager_user_id: uuid.UUID | None = None,
    *,
    name: str = "Test System",
    system_type: str = "web_application",
    base_url: str = "https://example.com",
    is_active: bool = True,
) -> dict:
    """Minimal system record dict."""
    return {
        "id": uuid.uuid4(),
        "company_id": company_id,
        "name": name,
        "description": "Automated test system",
        "system_type": system_type,
        "base_url": base_url,
        "system_manager_id": manager_user_id,
        "industry_domain": None,
        "is_active": is_active,
        "settings": None,
        "is_deleted": False,
        "deleted_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Requirement factories
# ─────────────────────────────────────────────────────────────────────────────

def create_requirement(
    system_id: uuid.UUID,
    company_id: uuid.UUID,
    *,
    title: str = "User must be able to log in",
    description: str = "Given a valid username and password, the user should reach the dashboard.",
    status: str = "active",
    priority: str = "high",
    business_domain: str | None = None,
    created_by: uuid.UUID | None = None,
) -> dict:
    """Minimal requirement record dict."""
    return {
        "id": uuid.uuid4(),
        "system_id": system_id,
        "company_id": company_id,
        "title": title,
        "description": description,
        "source_type": "manual",
        "source_reference": None,
        "business_domain": business_domain,
        "priority": priority,
        "status": status,
        "tags": None,
        "created_by": created_by,
        "is_deleted": False,
        "deleted_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test script factories
# ─────────────────────────────────────────────────────────────────────────────

def create_test_script(
    system_id: uuid.UUID,
    requirement_id: uuid.UUID | None = None,
    *,
    company_id: uuid.UUID | None = None,
    title: str = "Login Test Script",
    status: str = "draft",
    export_format: str = "playwright",
    script_content: str | None = "// placeholder",
    ai_generated: bool = False,
    created_by: uuid.UUID | None = None,
) -> dict:
    """Minimal test script record dict."""
    cid = company_id or uuid.uuid4()
    return {
        "id": uuid.uuid4(),
        "requirement_id": requirement_id,
        "system_id": system_id,
        "company_id": cid,
        "title": title,
        "description": None,
        "version": 1,
        "status": status,
        "export_format": export_format,
        "script_content": script_content,
        "rendered_content": None,
        "ai_generated": ai_generated,
        "ai_model_version": None,
        "approved_by": None,
        "approved_at": None,
        "business_domain": None,
        "tags": None,
        "created_by": created_by,
        "is_deleted": False,
        "deleted_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test cycle factories
# ─────────────────────────────────────────────────────────────────────────────

def create_test_cycle(
    system_id: uuid.UUID,
    *,
    company_id: uuid.UUID | None = None,
    name: str = "Sprint 1 Test Cycle",
    status: str = "planned",
    created_by: uuid.UUID | None = None,
) -> dict:
    """Minimal test cycle record dict."""
    return {
        "id": uuid.uuid4(),
        "system_id": system_id,
        "company_id": company_id or uuid.uuid4(),
        "name": name,
        "description": None,
        "status": status,
        "planned_start": None,
        "planned_end": None,
        "actual_start": None,
        "actual_end": None,
        "lead_user_id": None,
        "created_by": created_by,
        "created_at": _now(),
        "updated_at": _now(),
    }


def create_test_assignment(
    cycle_id: uuid.UUID,
    script_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    status: str = "pending",
) -> dict:
    """Minimal test assignment record dict."""
    return {
        "id": uuid.uuid4(),
        "test_cycle_id": cycle_id,
        "test_script_id": script_id,
        "assigned_to": user_id,
        "assigned_by": user_id,
        "due_date": None,
        "status": status,
        "assigned_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Agent run factories
# ─────────────────────────────────────────────────────────────────────────────

def create_agent_run(
    company_id: uuid.UUID,
    system_id: uuid.UUID | None = None,
    *,
    agent_type: str = "crawl",
    status: str = "pending",
    triggered_by_user_id: uuid.UUID | None = None,
    input_config: dict | None = None,
) -> dict:
    """Minimal agent run record dict."""
    return {
        "id": uuid.uuid4(),
        "company_id": company_id,
        "system_id": system_id,
        "agent_type": agent_type,
        "status": status,
        "trigger_type": "manual",
        "triggered_by_user_id": triggered_by_user_id,
        "scheduled_job_id": None,
        "service_bus_message_id": None,
        "input_config": input_config or {},
        "output_summary": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_cost_usd": None,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler factories
# ─────────────────────────────────────────────────────────────────────────────

def create_scheduled_job(
    system_id: uuid.UUID,
    *,
    company_id: uuid.UUID | None = None,
    schedule_type: str = "recurring",
    cron_expression: str = "0 9 * * 1",
    agent_type: str = "crawl",
    name: str = "Weekly Crawl",
    is_active: bool = True,
    next_run_at: datetime | None = None,
    input_config: dict | None = None,
) -> dict:
    """Minimal scheduled job record dict."""
    return {
        "id": uuid.uuid4(),
        "company_id": company_id or uuid.uuid4(),
        "system_id": system_id,
        "created_by": None,
        "name": name,
        "description": None,
        "agent_type": agent_type,
        "schedule_type": schedule_type,
        "cron_expression": cron_expression,
        "timezone": "UTC",
        "run_at": None,
        "job_config": input_config or {"base_url": "https://example.com"},
        "is_active": is_active,
        "max_failures": 3,
        "consecutive_failures": 0,
        "next_run_at": next_run_at,
        "last_run_at": None,
        "last_run_status": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Evidence factories
# ─────────────────────────────────────────────────────────────────────────────

def create_execution_run(
    agent_run_id: uuid.UUID,
    *,
    test_script_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    status: str = "running",
    test_result_id: uuid.UUID | None = None,
) -> dict:
    """Minimal execution run record dict."""
    return {
        "id": uuid.uuid4(),
        "test_result_id": test_result_id,
        "agent_run_id": agent_run_id,
        "test_script_id": test_script_id,
        "company_id": company_id or uuid.uuid4(),
        "status": status,
        "total_steps": 0,
        "passed_steps": 0,
        "failed_steps": 0,
        "evidence_pdf_blob_url": None,
        "started_at": _now(),
        "completed_at": None,
        "created_at": _now(),
    }


def create_execution_step(
    execution_run_id: uuid.UUID,
    step_number: int = 1,
    *,
    outcome: str = "passed",
    screenshot_blob_url: str | None = None,
) -> dict:
    """Minimal execution step result record dict."""
    return {
        "id": uuid.uuid4(),
        "execution_run_id": execution_run_id,
        "step_number": step_number,
        "step_description": f"Step {step_number}: Navigate to login page",
        "action": "navigate",
        "locator": "//input[@name='username']",
        "input_value": None,
        "expected_result": "Login page is displayed",
        "actual_result": "Login page loaded successfully",
        "outcome": outcome,
        "screenshot_blob_url": screenshot_blob_url,
        "error_message": None,
        "duration_ms": 250,
        "executed_at": _now(),
    }
