"""Systems router — filtered list, stats, assign-manager, system team."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import (
    Permission,
    can_manage_company,
    require_system_access,
)
from app.dependencies import get_db, get_current_user_id, get_current_company_id
from app.schemas.system import (
    AssignManagerBody,
    SystemCreate,
    SystemDetailRead,
    SystemRead,
    SystemUpdate,
)
from app.services.system_service import SystemService
from app.services.user_service import UserService

router = APIRouter(tags=["systems"])


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get("/systems", response_model=list[SystemRead])
async def list_systems(
    request: Request,
    system_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SystemRead]:
    company_id = get_current_company_id(request)
    return await SystemService(db).list_systems_filtered(
        company_id=company_id,
        current_user=current_user,
        system_type=system_type,
        is_active=is_active,
        search=search,
    )


@router.post("/systems", response_model=SystemRead, status_code=201, dependencies=[can_manage_company])
async def create_system(
    body: SystemCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SystemRead:
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await SystemService(db).create_system(
        body,
        company_id=company_id,
        created_by=user_id,
    )


# ── Detail / Update / Delete ──────────────────────────────────────────────────

@router.get("/systems/{system_id}", response_model=SystemRead)
async def get_system(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.SYSTEM_READ),
) -> SystemRead:
    return await SystemService(db).get_system(system_id)


@router.get("/systems/{system_id}/detail", response_model=SystemDetailRead)
async def get_system_detail(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.SYSTEM_READ),
) -> SystemDetailRead:
    return await SystemService(db).get_system_detail(system_id)


@router.patch("/systems/{system_id}", response_model=SystemRead)
async def update_system(
    system_id: UUID,
    body: SystemUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.SYSTEM_UPDATE),
) -> SystemRead:
    return await SystemService(db).update_system(system_id, body)


@router.put("/systems/{system_id}", response_model=SystemRead, include_in_schema=False)
async def update_system_put(
    system_id: UUID,
    body: SystemUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.SYSTEM_UPDATE),
) -> SystemRead:
    return await SystemService(db).update_system(system_id, body)


@router.delete("/systems/{system_id}", status_code=204, response_model=None)
async def delete_system(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.SYSTEM_DELETE),
) -> None:
    await SystemService(db).delete_system(system_id)


# ── Assign manager ────────────────────────────────────────────────────────────

@router.post("/systems/{system_id}/assign-manager", response_model=SystemRead)
async def assign_manager(
    system_id: UUID,
    body: AssignManagerBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.SYSTEM_UPDATE),
) -> SystemRead:
    company_id = get_current_company_id(request)
    return await SystemService(db).assign_manager(
        system_id=system_id,
        body=body,
        company_id=company_id,
    )


# ── System team ───────────────────────────────────────────────────────────────

@router.get("/systems/{system_id}/team")
async def get_system_team(
    system_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.SYSTEM_READ),
) -> list[dict]:
    return await UserService(db).list_system_team(system_id)
