from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system import System
from app.schemas.system import SystemCreate, SystemRead, SystemUpdate


class SystemService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_systems(self) -> list[SystemRead]:
        result = await self._db.execute(
            select(System).where(System.is_deleted.is_(False))
        )
        return [SystemRead.model_validate(s) for s in result.scalars().all()]

    async def create_system(self, body: SystemCreate, owner_id: UUID) -> SystemRead:
        data = body.model_dump()
        data["owner_id"] = owner_id
        data["base_url"] = str(data["base_url"])
        if data.get("crawl_config"):
            data["crawl_config"] = json.dumps(data["crawl_config"])
        if data.get("auth_config"):
            data["auth_config"] = json.dumps(data["auth_config"])
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
        if "base_url" in data:
            data["base_url"] = str(data["base_url"])
        if "crawl_config" in data:
            data["crawl_config"] = json.dumps(data["crawl_config"])
        if "auth_config" in data:
            data["auth_config"] = json.dumps(data["auth_config"])
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
