from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.test_cycle import TestExecution
from app.schemas.test_cycle import TestExecutionRead


class TestCycleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_script(self, script_id: UUID) -> list[TestExecutionRead]:
        result = await self._db.execute(
            select(TestExecution)
            .where(TestExecution.script_id == script_id)
            .options(selectinload(TestExecution.step_results))
            .order_by(TestExecution.started_at.desc())
        )
        return [TestExecutionRead.model_validate(e) for e in result.scalars().all()]

    async def get(self, execution_id: UUID) -> TestExecutionRead:
        result = await self._db.execute(
            select(TestExecution)
            .where(TestExecution.id == execution_id)
            .options(selectinload(TestExecution.step_results))
        )
        execution = result.scalar_one_or_none()
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        return TestExecutionRead.model_validate(execution)

    async def rerun(self, execution_id: UUID) -> TestExecutionRead:
        original = await self._db.get(TestExecution, execution_id)
        if not original:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        new_execution = TestExecution(
            script_id=original.script_id,
            system_id=original.system_id,
            company_id=original.company_id,
            triggered_by=original.triggered_by,
            status="pending",
        )
        self._db.add(new_execution)
        await self._db.flush()
        return TestExecutionRead.model_validate(new_execution)

    async def delete(self, execution_id: UUID) -> None:
        execution = await self._db.get(TestExecution, execution_id)
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        await self._db.delete(execution)
        await self._db.flush()
