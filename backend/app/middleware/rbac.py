from __future__ import annotations

from fastapi import HTTPException, Request, status


ALL_ROLES = frozenset({
    "platform_admin",
    "enterprise_admin",
    "company_admin",
    "system_manager",
    "qa_engineer",
    "viewer",
})


def assert_roles(request: Request, *required: str) -> None:
    """
    Raise 403 if the current user does not hold at least one of ``required`` roles.
    Call this inside route handlers for fine-grained in-handler checks.
    For route-level checks prefer the ``require_roles`` dependency in dependencies.py.
    """
    user_roles: list[str] = getattr(request.state, "roles", [])
    if not set(required).intersection(user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


def has_role(request: Request, *roles: str) -> bool:
    user_roles: list[str] = getattr(request.state, "roles", [])
    return bool(set(roles).intersection(user_roles))


def is_platform_admin(request: Request) -> bool:
    return has_role(request, "platform_admin")
