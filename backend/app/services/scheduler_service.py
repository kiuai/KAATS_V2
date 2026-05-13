from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduled_job import ScheduledJob, ScheduledJobRun
from app.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobRead,
    ScheduledJobRunRead,
    ScheduledJobUpdate,
)
from app.scheduler.cron_parser import compute_next_run, validate_cron


class SchedulerService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_jobs(self) -> list[ScheduledJobRead]:
        result = await self._db.execute(select(ScheduledJob))
        return [ScheduledJobRead.model_validate(j) for j in result.scalars().all()]

    async def create_job(self, body: ScheduledJobCreate, created_by: UUID) -> ScheduledJobRead:
        if not validate_cron(body.cron_expression):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid cron expression: {body.cron_expression}",
            )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        next_run = compute_next_run(body.cron_expression, body.timezone, now)
        job = ScheduledJob(
            **body.model_dump(),
            created_by=created_by,
            next_run_at=next_run,
        )
        self._db.add(job)
        await self._db.flush()
        return ScheduledJobRead.model_validate(job)

    async def get_job(self, job_id: UUID) -> ScheduledJobRead:
        job = await self._db.get(ScheduledJob, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return ScheduledJobRead.model_validate(job)

    async def update_job(self, job_id: UUID, body: ScheduledJobUpdate) -> ScheduledJobRead:
        job = await self._db.get(ScheduledJob, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        data = body.model_dump(exclude_none=True)
        cron = data.get("cron_expression", job.cron_expression)
        tz = data.get("timezone", job.timezone)
        if "cron_expression" in data or "timezone" in data:
            if not validate_cron(cron):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid cron expression: {cron}",
                )
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            data["next_run_at"] = compute_next_run(cron, tz, now)
        for field, value in data.items():
            setattr(job, field, value)
        await self._db.flush()
        return ScheduledJobRead.model_validate(job)

    async def delete_job(self, job_id: UUID) -> None:
        job = await self._db.get(ScheduledJob, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        await self._db.delete(job)
        await self._db.flush()

    async def trigger_now(self, job_id: UUID) -> ScheduledJobRunRead:
        job = await self._db.get(ScheduledJob, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        from app.scheduler.job_dispatcher import dispatch_job
        run = await dispatch_job(self._db, job)
        return ScheduledJobRunRead.model_validate(run)

    async def list_runs(self, job_id: UUID) -> list[ScheduledJobRunRead]:
        result = await self._db.execute(
            select(ScheduledJobRun)
            .where(ScheduledJobRun.job_id == job_id)
            .order_by(ScheduledJobRun.scheduled_for.desc())
        )
        return [ScheduledJobRunRead.model_validate(r) for r in result.scalars().all()]
