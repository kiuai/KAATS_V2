from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from app.models.enums import UserRoleEnum

# ── Permission enum ──────────────────────────────────────────────────────────


class Permission(str, Enum):
    # Tenant / Enterprise
    ENTERPRISE_READ = "enterprise:read"
    ENTERPRISE_MANAGE = "enterprise:manage"
    COMPANY_READ = "company:read"
    COMPANY_MANAGE = "company:manage"

    # User management
    USER_READ = "user:read"
    USER_INVITE = "user:invite"
    USER_UPDATE = "user:update"
    USER_DEACTIVATE = "user:deactivate"
    USER_ASSIGN_ROLE = "user:assign_role"

    # System management
    SYSTEM_READ = "system:read"
    SYSTEM_CREATE = "system:create"
    SYSTEM_UPDATE = "system:update"
    SYSTEM_DELETE = "system:delete"
    SYSTEM_MANAGE_OWN = "system:manage_own"  # SM: manage systems they own only

    # Requirements
    REQ_READ = "req:read"
    REQ_CREATE = "req:create"
    REQ_UPDATE = "req:update"
    REQ_DELETE = "req:delete"
    REQ_IMPORT = "req:import"

    # Test scripts
    SCRIPT_READ = "script:read"
    SCRIPT_CREATE = "script:create"
    SCRIPT_UPDATE = "script:update"
    SCRIPT_DELETE = "script:delete"
    SCRIPT_APPROVE = "script:approve"
    SCRIPT_EXPORT = "script:export"

    # Test cycles & execution
    CYCLE_READ = "cycle:read"
    CYCLE_CREATE = "cycle:create"
    CYCLE_UPDATE = "cycle:update"
    CYCLE_DELETE = "cycle:delete"
    ASSIGNMENT_CREATE = "assignment:create"
    ASSIGNMENT_UPDATE = "assignment:update"
    RESULT_READ = "result:read"
    RESULT_CREATE = "result:create"

    # Agents
    AGENT_CRAWL = "agent:crawl"
    AGENT_GENERATE = "agent:generate"
    AGENT_EXECUTE = "agent:execute"

    # Scheduler
    SCHEDULE_READ = "schedule:read"
    SCHEDULE_CREATE = "schedule:create"
    SCHEDULE_UPDATE = "schedule:update"
    SCHEDULE_DELETE = "schedule:delete"

    # Evidence
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_EXPORT = "evidence:export"

    # Reports
    REPORT_READ = "report:read"
    REPORT_EXPORT = "report:export"

    # Administration
    ADMIN_GLOBAL = "admin:global"
    ADMIN_ENTERPRISE = "admin:enterprise"
    ADMIN_COMPANY = "admin:company"
    AUDIT_LOG_READ = "audit:log_read"
    AI_USAGE_READ = "ai:usage_read"


_ALL: frozenset[Permission] = frozenset(Permission)

# ── Role → Permission mapping ────────────────────────────────────────────────

ROLE_PERMISSIONS: dict[UserRoleEnum, frozenset[Permission]] = {
    UserRoleEnum.GLOBAL_ADMIN: _ALL,
    UserRoleEnum.ENTERPRISE_ADMIN: _ALL - {Permission.ADMIN_GLOBAL},
    UserRoleEnum.COMPANY_ADMIN: frozenset(
        {
            Permission.COMPANY_READ,
            Permission.COMPANY_MANAGE,
            Permission.USER_READ,
            Permission.USER_INVITE,
            Permission.USER_UPDATE,
            Permission.USER_DEACTIVATE,
            Permission.USER_ASSIGN_ROLE,
            Permission.SYSTEM_READ,
            Permission.SYSTEM_CREATE,
            Permission.SYSTEM_UPDATE,
            Permission.SYSTEM_DELETE,
            Permission.REQ_READ,
            Permission.REQ_CREATE,
            Permission.REQ_UPDATE,
            Permission.REQ_DELETE,
            Permission.REQ_IMPORT,
            Permission.SCRIPT_READ,
            Permission.SCRIPT_CREATE,
            Permission.SCRIPT_UPDATE,
            Permission.SCRIPT_DELETE,
            Permission.SCRIPT_APPROVE,
            Permission.SCRIPT_EXPORT,
            Permission.CYCLE_READ,
            Permission.CYCLE_CREATE,
            Permission.CYCLE_UPDATE,
            Permission.CYCLE_DELETE,
            Permission.ASSIGNMENT_CREATE,
            Permission.ASSIGNMENT_UPDATE,
            Permission.RESULT_READ,
            Permission.RESULT_CREATE,
            Permission.AGENT_CRAWL,
            Permission.AGENT_GENERATE,
            Permission.AGENT_EXECUTE,
            Permission.SCHEDULE_READ,
            Permission.SCHEDULE_CREATE,
            Permission.SCHEDULE_UPDATE,
            Permission.SCHEDULE_DELETE,
            Permission.EVIDENCE_READ,
            Permission.EVIDENCE_EXPORT,
            Permission.REPORT_READ,
            Permission.REPORT_EXPORT,
            Permission.ADMIN_COMPANY,
            Permission.AI_USAGE_READ,
        }
    ),
    UserRoleEnum.SYSTEM_MANAGER: frozenset(
        {
            Permission.SYSTEM_READ,
            Permission.SYSTEM_MANAGE_OWN,
            Permission.REQ_READ,
            Permission.REQ_CREATE,
            Permission.REQ_UPDATE,
            Permission.REQ_DELETE,
            Permission.REQ_IMPORT,
            Permission.SCRIPT_READ,
            Permission.SCRIPT_CREATE,
            Permission.SCRIPT_UPDATE,
            Permission.SCRIPT_APPROVE,
            Permission.SCRIPT_EXPORT,
            Permission.CYCLE_READ,
            Permission.CYCLE_CREATE,
            Permission.ASSIGNMENT_CREATE,
            Permission.RESULT_READ,
            Permission.AGENT_CRAWL,
            Permission.AGENT_GENERATE,
            Permission.AGENT_EXECUTE,
            Permission.SCHEDULE_READ,
            Permission.SCHEDULE_CREATE,
            Permission.SCHEDULE_UPDATE,
            Permission.SCHEDULE_DELETE,
            Permission.EVIDENCE_READ,
            Permission.REPORT_READ,
            Permission.REPORT_EXPORT,
            Permission.USER_READ,
            Permission.AI_USAGE_READ,
        }
    ),
    UserRoleEnum.VALIDATION_LEAD: frozenset(
        {
            Permission.CYCLE_READ,
            Permission.CYCLE_CREATE,
            Permission.CYCLE_UPDATE,
            Permission.CYCLE_DELETE,
            Permission.ASSIGNMENT_CREATE,
            Permission.ASSIGNMENT_UPDATE,
            Permission.SCRIPT_READ,
            Permission.SCRIPT_APPROVE,
            Permission.SCRIPT_EXPORT,
            Permission.REQ_READ,
            Permission.RESULT_READ,
            Permission.REPORT_READ,
            Permission.REPORT_EXPORT,
            Permission.EVIDENCE_READ,
            Permission.AGENT_EXECUTE,
            Permission.USER_READ,
        }
    ),
    UserRoleEnum.QA: frozenset(
        {
            Permission.RESULT_READ,
            Permission.RESULT_CREATE,
            Permission.ASSIGNMENT_UPDATE,
            Permission.SCRIPT_READ,
            Permission.REQ_READ,
            Permission.EVIDENCE_READ,
            Permission.REPORT_READ,
            Permission.USER_READ,
            Permission.AGENT_CRAWL,
            Permission.AGENT_GENERATE,
            Permission.AGENT_EXECUTE,
        }
    ),
    UserRoleEnum.VALIDATION_TESTER: frozenset(
        {
            Permission.SCRIPT_READ,
            Permission.SCRIPT_CREATE,
            Permission.SCRIPT_UPDATE,
            Permission.REQ_READ,
            Permission.RESULT_CREATE,
            Permission.ASSIGNMENT_UPDATE,
            Permission.EVIDENCE_READ,
            Permission.USER_READ,
        }
    ),
    UserRoleEnum.BPO: frozenset(
        {
            Permission.REQ_READ,
            Permission.SCRIPT_READ,
            Permission.SCRIPT_APPROVE,
            Permission.RESULT_READ,
            Permission.REPORT_READ,
            Permission.EVIDENCE_READ,
            Permission.USER_READ,
        }
    ),
}


# ── System ownership ─────────────────────────────────────────────────────────


def check_system_ownership(user: CurrentUser, system_id: UUID) -> bool:
    """
    Returns True if the user has management ownership over a specific system.

    - GLOBAL_ADMIN, ENTERPRISE_ADMIN, COMPANY_ADMIN: always own all systems in scope.
    - SYSTEM_MANAGER: only owns systems where UserRole.system_id == system_id.
    - All other roles: never own a system (cannot manage it).
    """
    if user.is_global_admin:
        return True

    _admin_roles = {
        UserRoleEnum.GLOBAL_ADMIN,
        UserRoleEnum.ENTERPRISE_ADMIN,
        UserRoleEnum.COMPANY_ADMIN,
    }

    for role in user.roles:
        try:
            role_enum = UserRoleEnum(role.role)
        except ValueError:
            continue

        if role_enum in _admin_roles:
            return True

        if role_enum == UserRoleEnum.SYSTEM_MANAGER and role.system_id == system_id:
            return True

    return False


# ── System-access dependency factory ─────────────────────────────────────────

# Permissions that require SYSTEM_MANAGER to own the system.
# (SM gets SYSTEM_READ company-wide but can only *manage* their own systems.)
_OWNERSHIP_GATED: frozenset[Permission] = frozenset(
    {
        Permission.SYSTEM_MANAGE_OWN,
        Permission.SYSTEM_UPDATE,
        Permission.SYSTEM_DELETE,
    }
)


def require_system_access(
    permission: Permission,
    system_id_param: str = "system_id",
) -> Any:
    """
    FastAPI dependency factory.

    Resolves the system from path params, verifies it belongs to the current
    company, checks the caller has ``permission``, and for SYSTEM_MANAGER also
    validates system ownership on ownership-gated permissions.
    Injects the resolved System into request.state.current_system.

    Usage::

        @router.put("/systems/{system_id}")
        async def update_system(
            system=Depends(require_system_access(Permission.SYSTEM_UPDATE)),
        ):
            ...
    """
    from app.auth.azure_ad import CurrentUser, get_current_user  # avoid circular at module load
    from app.database import get_session_factory
    from app.models.system import System

    async def _check(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
    ) -> System:
        raw_id = request.path_params.get(system_id_param)
        if raw_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing path parameter: {system_id_param}",
            )
        try:
            system_id = UUID(str(raw_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid system_id format",
            )

        factory = get_session_factory()
        async with factory() as db:
            system = await db.get(System, system_id)

        if system is None or system.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="System not found",
            )

        # Verify system is in a company the user can access.
        if not current_user.is_global_admin:
            if system.company_id not in current_user.accessible_company_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="System not found",  # Don't leak existence
                )

        # Check permission across all user roles.
        granted = False
        for role in current_user.roles:
            try:
                role_enum = UserRoleEnum(role.role)
            except ValueError:
                continue

            perms = ROLE_PERMISSIONS.get(role_enum, frozenset())
            if permission not in perms:
                continue

            # SYSTEM_MANAGER: ownership required for ownership-gated permissions.
            if (
                role_enum == UserRoleEnum.SYSTEM_MANAGER
                and permission in _OWNERSHIP_GATED
                and not check_system_ownership(current_user, system_id)
            ):
                continue

            granted = True
            break

        if current_user.is_global_admin:
            granted = True

        if not granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this system",
            )

        request.state.current_system = system
        return system

    return Depends(_check)


# ── Convenience role-based dependency aliases ────────────────────────────────
# These match the role codes stored in UserRole.role (UserRoleEnum values).
# Used on routes that haven't migrated to the Permission-based system yet.

from app.dependencies import require_roles  # noqa: E402  (intentional late import)

any_authenticated = require_roles(
    UserRoleEnum.GLOBAL_ADMIN,
    UserRoleEnum.ENTERPRISE_ADMIN,
    UserRoleEnum.COMPANY_ADMIN,
    UserRoleEnum.SYSTEM_MANAGER,
    UserRoleEnum.VALIDATION_LEAD,
    UserRoleEnum.QA,
    UserRoleEnum.VALIDATION_TESTER,
    UserRoleEnum.BPO,
)

can_run_agents = require_roles(
    UserRoleEnum.GLOBAL_ADMIN,
    UserRoleEnum.ENTERPRISE_ADMIN,
    UserRoleEnum.COMPANY_ADMIN,
    UserRoleEnum.SYSTEM_MANAGER,
    UserRoleEnum.QA,
    UserRoleEnum.VALIDATION_LEAD,
)

can_manage_content = require_roles(
    UserRoleEnum.GLOBAL_ADMIN,
    UserRoleEnum.ENTERPRISE_ADMIN,
    UserRoleEnum.COMPANY_ADMIN,
    UserRoleEnum.SYSTEM_MANAGER,
)

can_manage_company = require_roles(
    UserRoleEnum.GLOBAL_ADMIN,
    UserRoleEnum.ENTERPRISE_ADMIN,
    UserRoleEnum.COMPANY_ADMIN,
)

platform_admin_only = require_roles(UserRoleEnum.GLOBAL_ADMIN)

can_read_audit = require_roles(
    UserRoleEnum.GLOBAL_ADMIN,
    UserRoleEnum.ENTERPRISE_ADMIN,
)
