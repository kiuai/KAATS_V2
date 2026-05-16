"""Users router — company-scoped list, roles CRUD, system team, deactivation."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import can_manage_company
from app.dependencies import get_current_company_id, get_current_user_id, get_db
from app.schemas.user import UserCreate, UserRead, UserRoleAssign, UserRoleRead, UserUpdate
from app.services.audit_service import AuditService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


# ── Self ──────────────────────────────────────────────────────────────────────


@router.get("/me", response_model=UserRead)
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserRead:
    return await UserService(db).get_user_with_roles(current_user.user.id)


# ── List ──────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[UserRead])
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[UserRead]:
    company_id = get_current_company_id(request)
    return await UserService(db).list_users_for_company(company_id)


# ── Invite ────────────────────────────────────────────────────────────────────


@router.post("/invite", response_model=UserRead, status_code=201, dependencies=[can_manage_company])
async def invite_user(
    body: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserRead:
    """Invite a new user without an initial role (use /invite-with-role for full setup)."""
    return await UserService(db).invite_user(body)


@router.post(
    "/invite-with-role", response_model=UserRead, status_code=201, dependencies=[can_manage_company]
)
async def invite_user_with_role(
    body: UserCreate,
    initial_role: UserRoleAssign,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserRead:
    invited_by = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await UserService(db).invite_user_with_role(
        body=body,
        initial_role=initial_role,
        invited_by=invited_by,
        company_id=company_id,
    )


# ── Read / Update / Deactivate ────────────────────────────────────────────────


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserRead:
    return await UserService(db).get_user_with_roles(user_id)


@router.patch("/{user_id}", response_model=UserRead, dependencies=[can_manage_company])
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    return await UserService(db).update_user(user_id, body)


@router.put(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[can_manage_company],
    include_in_schema=False,
)
async def update_user_put(
    user_id: UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    return await UserService(db).update_user(user_id, body)


@router.delete(
    "/{user_id}", status_code=204, response_model=None, dependencies=[can_manage_company]
)
async def deactivate_user(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    await UserService(db).deactivate_user(user_id, actor=current_user)
    await AuditService(db).log(
        event_type="user.deactivated",
        actor_user_id=current_user.user.id,
        actor_email=current_user.user.email,
        company_id=getattr(request.state, "company_id", None),
        resource_type="user",
        resource_id=str(user_id),
        request=request,
    )


# ── Roles ─────────────────────────────────────────────────────────────────────


@router.get("/{user_id}/roles", response_model=list[UserRoleRead])
async def get_roles(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[UserRoleRead]:
    return await UserService(db).get_roles(user_id)


@router.post(
    "/{user_id}/roles",
    response_model=UserRoleRead,
    status_code=201,
    dependencies=[can_manage_company],
)
async def assign_role(
    user_id: UUID,
    body: UserRoleAssign,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UserRoleRead:
    granted_by = get_current_user_id(request)
    result = await UserService(db).assign_role(
        user_id=user_id,
        body=body,
        granted_by=granted_by,
        actor_roles=current_user.roles,
    )
    await AuditService(db).log(
        event_type="user.role_assigned",
        actor_user_id=current_user.user.id,
        actor_email=current_user.user.email,
        company_id=getattr(request.state, "company_id", None),
        resource_type="user",
        resource_id=str(user_id),
        changes={
            "after": {
                "role": body.role,
                "company_id": str(body.company_id) if getattr(body, "company_id", None) else None,
            }
        },
        request=request,
    )
    return result


@router.delete(
    "/{user_id}/roles/{role_id}",
    status_code=204,
    response_model=None,
    dependencies=[can_manage_company],
)
async def revoke_role(
    user_id: UUID,
    role_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    await UserService(db).revoke_role(user_id, role_id)
    await AuditService(db).log(
        event_type="user.role_revoked",
        actor_user_id=current_user.user.id,
        actor_email=current_user.user.email,
        company_id=getattr(request.state, "company_id", None),
        resource_type="user",
        resource_id=str(user_id),
        changes={"before": {"role_id": str(role_id)}},
        request=request,
    )
