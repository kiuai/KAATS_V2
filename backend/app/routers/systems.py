from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_manage_content
from app.dependencies import get_db, get_current_user_id
from app.schemas.system import SystemCreate, SystemRead, SystemUpdate
from app.services.system_service import SystemService

router = APIRouter(prefix="/systems", tags=["systems"])


@router.get("", response_model=list[SystemRead], dependencies=[any_authenticated])
async def list_systems(db: AsyncSession = Depends(get_db)) -> list[SystemRead]:
    return await SystemService(db).list_systems()


@router.post("", response_model=SystemRead, status_code=201, dependencies=[can_manage_content])
async def create_system(
    body: SystemCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> SystemRead:
    owner_id = get_current_user_id(request)
    return await SystemService(db).create_system(body, owner_id=owner_id)


@router.get("/{system_id}", response_model=SystemRead, dependencies=[any_authenticated])
async def get_system(system_id: UUID, db: AsyncSession = Depends(get_db)) -> SystemRead:
    return await SystemService(db).get_system(system_id)


@router.put("/{system_id}", response_model=SystemRead, dependencies=[can_manage_content])
async def update_system(
    system_id: UUID, body: SystemUpdate, db: AsyncSession = Depends(get_db)
) -> SystemRead:
    return await SystemService(db).update_system(system_id, body)


@router.delete("/{system_id}", status_code=204, dependencies=[can_manage_content])
async def delete_system(system_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await SystemService(db).delete_system(system_id)
