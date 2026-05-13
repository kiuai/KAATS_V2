from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserCompanyRole
from app.schemas.user import RoleAssign, UserCreate, UserRead, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_user(self, user_id: UUID) -> UserRead:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserRead.model_validate(user)

    async def list_users(self) -> list[UserRead]:
        result = await self._db.execute(select(User).where(User.is_active.is_(True)))
        return [UserRead.model_validate(u) for u in result.scalars().all()]

    async def invite_user(self, body: UserCreate) -> UserRead:
        existing = await self._db.execute(select(User).where(User.email == body.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        user = User(**body.model_dump())
        self._db.add(user)
        await self._db.flush()
        return UserRead.model_validate(user)

    async def update_user(self, user_id: UUID, body: UserUpdate) -> UserRead:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        await self._db.flush()
        return UserRead.model_validate(user)

    async def assign_role(self, user_id: UUID, body: RoleAssign) -> UserRead:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        # Role assignment is handled via UserCompanyRole — see DATA_MODEL.md
        return UserRead.model_validate(user)

    async def remove_user(self, user_id: UUID) -> None:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        user.is_active = False
        await self._db.flush()
