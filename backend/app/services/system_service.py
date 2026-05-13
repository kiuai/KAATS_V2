from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import System
from app.schemas.system import SystemCreate, SystemRead, SystemUpdate


class SystemService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_systems(self, company_id: UUID) -> list[SystemRead]:
        result = await self._db.execute(
            select(System).where(
                System.company_id == company_id,
                System.is_deleted == False,  # noqa: E712
            )
        )
        return [SystemRead.model_validate(s) for s in result.scalars().all()]

    async def create_system(self, body: SystemCreate, company_id: UUID, created_by: UUID) -> SystemRead:
        data = body.model_dump()
        data["company_id"] = company_id
        data["system_manager_id"] = data.pop("system_manager_id", None) or created_by
        if "system_type" in data and hasattr(data["system_type"], "value"):
            data["system_type"] = data["system_type"].value
        system = System(**data)
        self._db.add(system)
        await self._db.flush()
        return SystemRead.model_validate(system)

    async def get_system(self, system_id: UUID) -> SystemRead:
        system = await self._db.get(System, system_id)
        if not system or system.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
        return SystemRead.model_validate(system)

    async def update_system(self, system_id: UUID, body: SystemUpdate) -> SystemRead:
        system = await self._db.get(System, system_id)
        if not system or system.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
        data = body.model_dump(exclude_none=True)
        if "system_type" in data and hasattr(data["system_type"], "value"):
            data["system_type"] = data["system_type"].value
        for field, value in data.items():
            setattr(system, field, value)
        await self._db.flush()
        return SystemRead.model_validate(system)

    async def delete_system(self, system_id: UUID) -> None:
        system = await self._db.get(System, system_id)
        if not system or system.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
        system.is_deleted = True
        await self._db.flush()
