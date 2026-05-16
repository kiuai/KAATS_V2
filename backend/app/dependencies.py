from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db as _get_db


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an AsyncSession scoped to the current tenant."""
    company_id: str | None = getattr(request.state, "company_id", None)
    async for session in _get_db(company_id=company_id):
        yield session


def get_current_user_id(request: Request) -> UUID:
    user_id: UUID | None = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing user context")
    return user_id


def get_current_company_id(request: Request) -> UUID:
    company_id: UUID | None = getattr(request.state, "company_id", None)
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing company context — supply X-Company-Slug header",
        )
    return company_id


def get_current_roles(request: Request) -> list[str]:
    return getattr(request.state, "roles", [])


def require_roles(*roles: str):
    """
    FastAPI dependency factory.

    Global admins (is_global_admin=True in the DB) bypass all role checks.
    For everyone else, the caller must have at least one of the listed roles.

    Usage::

        @router.post("/foo")
        async def create_foo(_: None = Depends(require_roles("qa_engineer", "system_manager"))):
            ...
    """
    # Late import to avoid circular: azure_ad → permissions → dependencies → azure_ad
    from app.auth.azure_ad import CurrentUser, get_current_user  # noqa: PLC0415

    allowed = set(roles)

    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> None:
        # Global admins pass every role gate without needing an explicit UserRole record.
        if current_user.is_global_admin:
            return
        user_roles: set[str] = {r.role for r in current_user.roles}
        if not allowed.intersection(user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    return Depends(_check)
