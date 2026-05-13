from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_manage_company
from app.dependencies import get_db, get_current_user_id
from app.schemas.user import RoleAssign, UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead, dependencies=[any_authenticated])
async def get_me(request: Request, db: AsyncSession = Depends(get_db)) -> UserRead:
    user_id = get_current_user_id(request)
    return await UserService(db).get_user(user_id)


@router.get("", response_model=list[UserRead], dependencies=[any_authenticated])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserRead]:
    return await UserService(db).list_users()


@router.post("/invite", response_model=UserRead, status_code=201, dependencies=[can_manage_company])
async def invite_user(body: UserCreate, db: AsyncSession = Depends(get_db)) -> UserRead:
    return await UserService(db).invite_user(body)


@router.put("/{user_id}", response_model=UserRead, dependencies=[can_manage_company])
async def update_user(
    user_id: UUID, body: UserUpdate, db: AsyncSession = Depends(get_db)
) -> UserRead:
    return await UserService(db).update_user(user_id, body)


@router.put("/{user_id}/role", response_model=UserRead, dependencies=[can_manage_company])
async def assign_role(
    user_id: UUID, body: RoleAssign, db: AsyncSession = Depends(get_db)
) -> UserRead:
    return await UserService(db).assign_role(user_id, body)


@router.delete("/{user_id}", status_code=204, response_model=None, dependencies=[can_manage_company])
async def remove_user(user_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await UserService(db).remove_user(user_id)
