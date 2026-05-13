from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementUpdate


class RequirementService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_system(self, system_id: UUID) -> list[RequirementRead]:
        result = await self._db.execute(
            select(Requirement).where(Requirement.system_id == system_id)
        )
        return [RequirementRead.model_validate(r) for r in result.scalars().all()]

    async def create(self, system_id: UUID, body: RequirementCreate) -> RequirementRead:
        req = Requirement(system_id=system_id, **body.model_dump())
        self._db.add(req)
        await self._db.flush()
        return RequirementRead.model_validate(req)

    async def get(self, requirement_id: UUID) -> RequirementRead:
        req = await self._db.get(Requirement, requirement_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
        return RequirementRead.model_validate(req)

    async def update(self, requirement_id: UUID, body: RequirementUpdate) -> RequirementRead:
        req = await self._db.get(Requirement, requirement_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(req, field, value)
        await self._db.flush()
        return RequirementRead.model_validate(req)

    async def delete(self, requirement_id: UUID) -> None:
        req = await self._db.get(Requirement, requirement_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
        await self._db.delete(req)
        await self._db.flush()

    async def approve(self, requirement_id: UUID) -> RequirementRead:
        req = await self._db.get(Requirement, requirement_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
        req.status = "approved"
        await self._db.flush()
        return RequirementRead.model_validate(req)
