from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.test_script import TestScript
from app.schemas.test_script import TestScriptCreate, TestScriptRead, TestScriptUpdate


class TestScriptService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_system(self, system_id: UUID) -> list[TestScriptRead]:
        result = await self._db.execute(
            select(TestScript)
            .where(TestScript.system_id == system_id)
            .options(selectinload(TestScript.cases))
        )
        return [TestScriptRead.model_validate(s) for s in result.scalars().all()]

    async def create(self, system_id: UUID, body: TestScriptCreate) -> TestScriptRead:
        script = TestScript(system_id=system_id, **body.model_dump())
        self._db.add(script)
        await self._db.flush()
        return TestScriptRead.model_validate(script)

    async def get(self, script_id: UUID) -> TestScriptRead:
        result = await self._db.execute(
            select(TestScript)
            .where(TestScript.id == script_id)
            .options(selectinload(TestScript.cases))
        )
        script = result.scalar_one_or_none()
        if not script:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
        return TestScriptRead.model_validate(script)

    async def update(self, script_id: UUID, body: TestScriptUpdate) -> TestScriptRead:
        script = await self._db.get(TestScript, script_id)
        if not script:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(script, field, value)
        await self._db.flush()
        return TestScriptRead.model_validate(script)

    async def delete(self, script_id: UUID) -> None:
        script = await self._db.get(TestScript, script_id)
        if not script:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
        await self._db.delete(script)
        await self._db.flush()

    async def export(self, script_id: UUID, fmt: str) -> tuple[bytes, str, str]:
        from app.exporters.base import get_exporter
        script = await self.get(script_id)
        exporter = get_exporter(fmt)
        content = exporter.export(script)
        return content, exporter.media_type, exporter.filename(script)
