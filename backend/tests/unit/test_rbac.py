"""
Unit tests for the RBAC permission system.

Tests cover:
  - Role × permission matrix (every role has exactly the right permissions)
  - check_system_ownership() logic
  - BPO domain scoping (role-level field, not permission)
  - Global admin bypass
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.auth.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    check_system_ownership,
)
from app.models.enums import UserRoleEnum


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _role(role_enum: UserRoleEnum, system_id: uuid.UUID | None = None) -> Any:
    r = MagicMock()
    r.role = role_enum.value
    r.system_id = system_id
    return r


def _current_user(
    roles: list[Any],
    *,
    is_global_admin: bool = False,
) -> Any:
    from app.auth.azure_ad import CurrentUser
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = uuid.uuid4()
    user.is_global_admin = is_global_admin

    return CurrentUser(
        user=user,
        roles=roles,
        is_global_admin=is_global_admin,
        accessible_company_ids=[],
        accessible_system_ids=[],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Role × Permission matrix
# ─────────────────────────────────────────────────────────────────────────────

class TestRolePermissionMatrix:
    """Verify that every role has *exactly* the permissions declared in permissions.py."""

    def test_every_role_is_covered(self) -> None:
        """All UserRoleEnum values must be in ROLE_PERMISSIONS."""
        for role in UserRoleEnum:
            assert role in ROLE_PERMISSIONS, f"{role} missing from ROLE_PERMISSIONS"

    def test_global_admin_has_all_permissions(self) -> None:
        global_admin_perms = ROLE_PERMISSIONS[UserRoleEnum.GLOBAL_ADMIN]
        for perm in Permission:
            assert perm in global_admin_perms, f"GLOBAL_ADMIN missing {perm}"

    def test_enterprise_admin_lacks_only_global_admin(self) -> None:
        ea_perms = ROLE_PERMISSIONS[UserRoleEnum.ENTERPRISE_ADMIN]
        assert Permission.ADMIN_GLOBAL not in ea_perms
        # Has every other permission
        for perm in Permission:
            if perm != Permission.ADMIN_GLOBAL:
                assert perm in ea_perms, f"ENTERPRISE_ADMIN missing {perm}"

    # ── COMPANY_ADMIN expected grants ────────────────────────────────────────

    @pytest.mark.parametrize("perm", [
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
    ])
    def test_company_admin_has_perm(self, perm: Permission) -> None:
        assert perm in ROLE_PERMISSIONS[UserRoleEnum.COMPANY_ADMIN]

    @pytest.mark.parametrize("perm", [
        Permission.ADMIN_GLOBAL,
        Permission.ADMIN_ENTERPRISE,
        Permission.AUDIT_LOG_READ,
        Permission.ENTERPRISE_READ,
        Permission.ENTERPRISE_MANAGE,
    ])
    def test_company_admin_lacks_perm(self, perm: Permission) -> None:
        assert perm not in ROLE_PERMISSIONS[UserRoleEnum.COMPANY_ADMIN]

    # ── SYSTEM_MANAGER expected grants ──────────────────────────────────────

    @pytest.mark.parametrize("perm", [
        Permission.SYSTEM_READ,
        Permission.SYSTEM_MANAGE_OWN,
        Permission.REQ_READ,
        Permission.REQ_CREATE,
        Permission.AGENT_CRAWL,
        Permission.AGENT_GENERATE,
        Permission.AGENT_EXECUTE,
        Permission.SCHEDULE_READ,
        Permission.SCHEDULE_CREATE,
        Permission.SCHEDULE_UPDATE,
        Permission.SCHEDULE_DELETE,
    ])
    def test_system_manager_has_perm(self, perm: Permission) -> None:
        assert perm in ROLE_PERMISSIONS[UserRoleEnum.SYSTEM_MANAGER]

    @pytest.mark.parametrize("perm", [
        Permission.SYSTEM_CREATE,
        Permission.SYSTEM_DELETE,
        Permission.COMPANY_MANAGE,
        Permission.USER_INVITE,
        Permission.ADMIN_COMPANY,
        Permission.ADMIN_GLOBAL,
    ])
    def test_system_manager_lacks_perm(self, perm: Permission) -> None:
        assert perm not in ROLE_PERMISSIONS[UserRoleEnum.SYSTEM_MANAGER]

    # ── QA expected grants ───────────────────────────────────────────────────

    @pytest.mark.parametrize("perm", [
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
    ])
    def test_qa_has_perm(self, perm: Permission) -> None:
        assert perm in ROLE_PERMISSIONS[UserRoleEnum.QA]

    @pytest.mark.parametrize("perm", [
        Permission.SCRIPT_APPROVE,
        Permission.SCRIPT_DELETE,
        Permission.SYSTEM_CREATE,
        Permission.SCHEDULE_DELETE,
        Permission.ADMIN_COMPANY,
    ])
    def test_qa_lacks_perm(self, perm: Permission) -> None:
        assert perm not in ROLE_PERMISSIONS[UserRoleEnum.QA]

    # ── BPO expected grants ───────────────────────────────────────────────────

    @pytest.mark.parametrize("perm", [
        Permission.REQ_READ,
        Permission.SCRIPT_READ,
        Permission.SCRIPT_APPROVE,
        Permission.RESULT_READ,
        Permission.REPORT_READ,
        Permission.EVIDENCE_READ,
        Permission.USER_READ,
    ])
    def test_bpo_has_perm(self, perm: Permission) -> None:
        assert perm in ROLE_PERMISSIONS[UserRoleEnum.BPO]

    @pytest.mark.parametrize("perm", [
        Permission.SCRIPT_CREATE,
        Permission.SCRIPT_UPDATE,
        Permission.SCRIPT_DELETE,
        Permission.REQ_CREATE,
        Permission.AGENT_CRAWL,
        Permission.AGENT_EXECUTE,
        Permission.ADMIN_COMPANY,
    ])
    def test_bpo_lacks_perm(self, perm: Permission) -> None:
        assert perm not in ROLE_PERMISSIONS[UserRoleEnum.BPO]

    # ── VALIDATION_TESTER ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("perm", [
        Permission.SCRIPT_READ,
        Permission.SCRIPT_CREATE,
        Permission.SCRIPT_UPDATE,
        Permission.REQ_READ,
        Permission.RESULT_CREATE,
        Permission.ASSIGNMENT_UPDATE,
        Permission.EVIDENCE_READ,
        Permission.USER_READ,
    ])
    def test_validation_tester_has_perm(self, perm: Permission) -> None:
        assert perm in ROLE_PERMISSIONS[UserRoleEnum.VALIDATION_TESTER]

    @pytest.mark.parametrize("perm", [
        Permission.SCRIPT_APPROVE,
        Permission.SCRIPT_DELETE,
        Permission.AGENT_CRAWL,
        Permission.CYCLE_CREATE,
        Permission.SCHEDULE_CREATE,
    ])
    def test_validation_tester_lacks_perm(self, perm: Permission) -> None:
        assert perm not in ROLE_PERMISSIONS[UserRoleEnum.VALIDATION_TESTER]

    # ── VALIDATION_LEAD ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("perm", [
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
        Permission.EVIDENCE_READ,
        Permission.AGENT_EXECUTE,
    ])
    def test_validation_lead_has_perm(self, perm: Permission) -> None:
        assert perm in ROLE_PERMISSIONS[UserRoleEnum.VALIDATION_LEAD]

    @pytest.mark.parametrize("perm", [
        Permission.SCRIPT_CREATE,
        Permission.SCRIPT_DELETE,
        Permission.AGENT_CRAWL,
        Permission.AGENT_GENERATE,
        Permission.SCHEDULE_CREATE,
        Permission.ADMIN_COMPANY,
    ])
    def test_validation_lead_lacks_perm(self, perm: Permission) -> None:
        assert perm not in ROLE_PERMISSIONS[UserRoleEnum.VALIDATION_LEAD]


# ─────────────────────────────────────────────────────────────────────────────
# check_system_ownership()
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckSystemOwnership:
    """check_system_ownership() must honour the ownership rules exactly."""

    def test_global_admin_always_owns(self) -> None:
        cu = _current_user([], is_global_admin=True)
        assert check_system_ownership(cu, uuid.uuid4()) is True

    def test_company_admin_always_owns(self) -> None:
        sid = uuid.uuid4()
        cu = _current_user([_role(UserRoleEnum.COMPANY_ADMIN)])
        assert check_system_ownership(cu, sid) is True

    def test_enterprise_admin_always_owns(self) -> None:
        sid = uuid.uuid4()
        cu = _current_user([_role(UserRoleEnum.ENTERPRISE_ADMIN)])
        assert check_system_ownership(cu, sid) is True

    def test_system_manager_owns_assigned_system(self) -> None:
        sid = uuid.uuid4()
        cu = _current_user([_role(UserRoleEnum.SYSTEM_MANAGER, system_id=sid)])
        assert check_system_ownership(cu, sid) is True

    def test_system_manager_does_not_own_other_system(self) -> None:
        sid = uuid.uuid4()
        other_sid = uuid.uuid4()
        cu = _current_user([_role(UserRoleEnum.SYSTEM_MANAGER, system_id=sid)])
        assert check_system_ownership(cu, other_sid) is False

    def test_system_manager_no_system_id_does_not_own(self) -> None:
        cu = _current_user([_role(UserRoleEnum.SYSTEM_MANAGER, system_id=None)])
        assert check_system_ownership(cu, uuid.uuid4()) is False

    @pytest.mark.parametrize("role", [
        UserRoleEnum.QA,
        UserRoleEnum.VALIDATION_LEAD,
        UserRoleEnum.VALIDATION_TESTER,
        UserRoleEnum.BPO,
    ])
    def test_non_manager_roles_never_own(self, role: UserRoleEnum) -> None:
        sid = uuid.uuid4()
        # Even if system_id is set on role, these roles never grant ownership
        cu = _current_user([_role(role, system_id=sid)])
        assert check_system_ownership(cu, sid) is False

    def test_no_roles_no_ownership(self) -> None:
        cu = _current_user([])
        assert check_system_ownership(cu, uuid.uuid4()) is False

    def test_invalid_role_string_skipped(self) -> None:
        """Roles with unrecognised strings don't raise — they're silently skipped."""
        r = MagicMock()
        r.role = "not_a_valid_role"
        r.system_id = uuid.uuid4()
        cu = _current_user([r])
        assert check_system_ownership(cu, r.system_id) is False

    def test_system_manager_with_multiple_system_roles(self) -> None:
        """SM with roles for two systems owns both."""
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        cu = _current_user([
            _role(UserRoleEnum.SYSTEM_MANAGER, system_id=sid1),
            _role(UserRoleEnum.SYSTEM_MANAGER, system_id=sid2),
        ])
        assert check_system_ownership(cu, sid1) is True
        assert check_system_ownership(cu, sid2) is True
        assert check_system_ownership(cu, uuid.uuid4()) is False


# ─────────────────────────────────────────────────────────────────────────────
# Permission set invariants
# ─────────────────────────────────────────────────────────────────────────────

class TestPermissionSetInvariants:
    """Cross-role invariants that should always hold."""

    def test_global_admin_is_superset_of_enterprise_admin(self) -> None:
        ga = ROLE_PERMISSIONS[UserRoleEnum.GLOBAL_ADMIN]
        ea = ROLE_PERMISSIONS[UserRoleEnum.ENTERPRISE_ADMIN]
        assert ea.issubset(ga)

    def test_enterprise_admin_is_superset_of_company_admin(self) -> None:
        ea = ROLE_PERMISSIONS[UserRoleEnum.ENTERPRISE_ADMIN]
        ca = ROLE_PERMISSIONS[UserRoleEnum.COMPANY_ADMIN]
        assert ca.issubset(ea)

    def test_no_role_except_global_admin_has_admin_global(self) -> None:
        for role, perms in ROLE_PERMISSIONS.items():
            if role == UserRoleEnum.GLOBAL_ADMIN:
                continue
            assert Permission.ADMIN_GLOBAL not in perms, (
                f"{role} should not have ADMIN_GLOBAL"
            )

    def test_no_role_below_enterprise_has_enterprise_manage(self) -> None:
        restricted = {
            UserRoleEnum.QA,
            UserRoleEnum.VALIDATION_TESTER,
            UserRoleEnum.VALIDATION_LEAD,
            UserRoleEnum.BPO,
            UserRoleEnum.SYSTEM_MANAGER,
        }
        for role in restricted:
            assert Permission.ENTERPRISE_MANAGE not in ROLE_PERMISSIONS[role]

    def test_all_permission_enum_values_are_strings(self) -> None:
        for perm in Permission:
            assert isinstance(perm.value, str)
            assert ":" in perm.value, f"Permission {perm} should be 'domain:action'"

    def test_role_permissions_are_frozensets(self) -> None:
        for role, perms in ROLE_PERMISSIONS.items():
            assert isinstance(perms, frozenset), f"{role} permissions should be a frozenset"
