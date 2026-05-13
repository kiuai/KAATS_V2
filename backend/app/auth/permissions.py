from __future__ import annotations

from app.dependencies import require_roles

# ── Convenience aliases matching the permission matrix in RBAC_MATRIX.md ──────

# Any authenticated user with at least viewer access
any_authenticated = require_roles(
    "platform_admin", "enterprise_admin", "company_admin",
    "system_manager", "qa_engineer", "viewer",
)

# Can trigger agents and run tests
can_run_agents = require_roles(
    "platform_admin", "enterprise_admin", "company_admin",
    "system_manager", "qa_engineer",
)

# Can manage systems, scheduled jobs, requirements, scripts
can_manage_content = require_roles(
    "platform_admin", "enterprise_admin", "company_admin", "system_manager",
)

# Can manage users and company settings
can_manage_company = require_roles(
    "platform_admin", "enterprise_admin", "company_admin",
)

# Platform admin only
platform_admin_only = require_roles("platform_admin")
