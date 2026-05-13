from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AgentType, ScheduleType
from app.models.scheduled_job import ScheduledJob, ScheduledJobRun
from app.scheduler.cron_parser import CronParser, compute_next_run
from app.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobRead,
    ScheduledJobRunRead,
    ScheduledJobUpdate,
)

_MAX_ACTIVE_JOBS_PER_SYSTEM = 20
_parser = CronParser()


class SchedulerService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── System-scoped CRUD ────────────────────────────────────────────────────

    async def create_scheduled_job(
        self,
        body: ScheduledJobCreate,
        system_id: UUID,
        created_by: UUID,
        company_id: UUID,
    ) -> ScheduledJobRead:
        self._validate_schedule(body.schedule_type, body.cron_expression, body.run_at)
        self._validate_job_config(body.agent_type, body.job_config or {})
        await self._check_active_job_limit(system_id, company_id)

        next_run_at = self._calculate_next_run(
            body.schedule_type, body.cron_expression, body.run_at, body.timezone
        )
        at_val = body.agent_type.value if hasattr(body.agent_type, "value") else body.agent_type
        st_val = body.schedule_type.value if hasattr(body.schedule_type, "value") else body.schedule_type

        job = ScheduledJob(
            company_id=company_id,
            system_id=system_id,
            created_by=created_by,
            name=body.name,
            description=body.description,
            agent_type=at_val,
            schedule_type=st_val,
            cron_expression=body.cron_expression,
            timezone=body.timezone,
            run_at=body.run_at.replace(tzinfo=None) if body.run_at else None,
            job_config=body.job_config,
            is_active=body.is_active,
            max_failures=body.max_failures,
            next_run_at=next_run_at,
        )
        self._db.add(job)
        await self._db.flush()
        return ScheduledJobRead.model_validate(job)

    async def get_scheduled_job(self, job_id: UUID, system_id: UUID) -> ScheduledJobRead:
        job = await self._get_or_404(job_id, system_id)
        return ScheduledJobRead.model_validate(job)

    async def update_scheduled_job(
        self,
        job_id: UUID,
        system_id: UUID,
        body: ScheduledJobUpdate,
    ) -> ScheduledJobRead:
        job = await self._get_or_404(job_id, system_id)
        data = body.model_dump(exclude_none=True)

        new_cron = data.get("cron_expression", job.cron_expression)
        new_tz = data.get("timezone", job.timezone)
        new_run_at = data.get("run_at", job.run_at)
        new_type = data.get("schedule_type", job.schedule_type)

        if "cron_expression" in data or "timezone" in data or "run_at" in data:
            self._validate_schedule(new_type, new_cron, new_run_at)
            data["next_run_at"] = self._calculate_next_run(new_type, new_cron, new_run_at, new_tz)

        if "job_config" in data:
            self._validate_job_config(job.agent_type, data["job_config"])

        for field, value in data.items():
            setattr(job, field, value)

        await self._db.flush()
        return ScheduledJobRead.model_validate(job)

    async def deactivate_scheduled_job(self, job_id: UUID, system_id: UUID) -> ScheduledJobRead:
        job = await self._get_or_404(job_id, system_id)
        job.is_active = False
        await self._db.flush()
        return ScheduledJobRead.model_validate(job)

    async def list_scheduled_jobs(self, system_id: UUID, company_id: UUID) -> list[ScheduledJobRead]:
        result = await self._db.execute(
            select(ScheduledJob)
            .where(
                ScheduledJob.system_id == system_id,
                ScheduledJob.company_id == company_id,
            )
            .order_by(ScheduledJob.created_at.desc())
        )
        return [ScheduledJobRead.model_validate(j) for j in result.scalars().all()]

    async def list_job_runs(self, job_id: UUID, system_id: UUID) -> list[ScheduledJobRunRead]:
        await self._get_or_404(job_id, system_id)
        result = await self._db.execute(
            select(ScheduledJobRun)
            .where(ScheduledJobRun.job_id == job_id)
            .order_by(ScheduledJobRun.scheduled_for.desc())
            .limit(100)
        )
        return [ScheduledJobRunRead.model_validate(r) for r in result.scalars().all()]

    async def trigger_now(self, job_id: UUID, system_id: UUID) -> ScheduledJobRunRead:
        job = await self._get_or_404(job_id, system_id)
        from app.scheduler.job_dispatcher import dispatch_scheduled_job
        run = await dispatch_scheduled_job(self._db, job)
        return ScheduledJobRunRead.model_validate(run)

    # ── Evaluator-facing methods ──────────────────────────────────────────────

    async def get_due_jobs(self) -> list[ScheduledJob]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await self._db.execute(
            select(ScheduledJob)
            .where(
                ScheduledJob.is_active == True,  # noqa: E712
                ScheduledJob.next_run_at <= now,
                (ScheduledJob.last_run_at.is_(None))
                | (ScheduledJob.last_run_at < ScheduledJob.next_run_at),
            )
            .order_by(ScheduledJob.next_run_at.asc())
        )
        return list(result.scalars().all())

    async def record_job_triggered(self, job: ScheduledJob, agent_run_id: UUID) -> ScheduledJobRun:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        run = ScheduledJobRun(
            job_id=job.id,
            agent_run_id=agent_run_id,
            status="triggered",
            scheduled_for=now,
        )
        self._db.add(run)
        job.last_run_at = now
        job.last_run_status = "pending"
        if job.schedule_type == ScheduleType.ONE_SHOT.value:
            job.is_active = False
        elif job.cron_expression:
            job.next_run_at = compute_next_run(job.cron_expression, job.timezone or "UTC", now)
        await self._db.flush()
        return run

    # ── Backwards-compatible shims ────────────────────────────────────────────

    async def list_jobs(self) -> list[ScheduledJobRead]:
        result = await self._db.execute(select(ScheduledJob))
        return [ScheduledJobRead.model_validate(j) for j in result.scalars().all()]

    async def create_job(self, body: ScheduledJobCreate, created_by: UUID) -> ScheduledJobRead:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cron = body.cron_expression or "0 0 * * *"
        tz = body.timezone or "UTC"
        next_run = compute_next_run(cron, tz, now)
        raw = body.model_dump()
        raw["agent_type"] = body.agent_type.value if hasattr(body.agent_type, "value") else body.agent_type
        raw["schedule_type"] = body.schedule_type.value if hasattr(body.schedule_type, "value") else body.schedule_type
        job = ScheduledJob(**raw, created_by=created_by, next_run_at=next_run)
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
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(job, field, value)
        await self._db.flush()
        return ScheduledJobRead.model_validate(job)

    async def delete_job(self, job_id: UUID) -> None:
        job = await self._db.get(ScheduledJob, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        await self._db.delete(job)
        await self._db.flush()

    async def list_runs(self, job_id: UUID) -> list[ScheduledJobRunRead]:
        result = await self._db.execute(
            select(ScheduledJobRun)
            .where(ScheduledJobRun.job_id == job_id)
            .order_by(ScheduledJobRun.scheduled_for.desc())
        )
        return [ScheduledJobRunRead.model_validate(r) for r in result.scalars().all()]

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get_or_404(self, job_id: UUID, system_id: UUID) -> ScheduledJob:
        job = await self._db.get(ScheduledJob, job_id)
        if not job or job.system_id != system_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduled job not found",
            )
        return job

    async def _check_active_job_limit(self, system_id: UUID, company_id: UUID) -> None:
        result = await self._db.execute(
            select(func.count(ScheduledJob.id)).where(
                ScheduledJob.system_id == system_id,
                ScheduledJob.company_id == company_id,
                ScheduledJob.is_active == True,  # noqa: E712
            )
        )
        count = result.scalar_one()
        if count >= _MAX_ACTIVE_JOBS_PER_SYSTEM:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Maximum of {_MAX_ACTIVE_JOBS_PER_SYSTEM} active scheduled jobs "
                    "per system reached. Deactivate an existing job first."
                ),
            )

    @staticmethod
    def _validate_schedule(
        schedule_type: str,
        cron_expression: str | None,
        run_at: datetime | None,
    ) -> None:
        st = schedule_type.value if hasattr(schedule_type, "value") else schedule_type

        if st == ScheduleType.RECURRING.value:
            if not cron_expression:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="cron_expression is required for RECURRING jobs",
                )
            if not _parser.validate(cron_expression):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid cron expression: {cron_expression!r}",
                )
            if not _parser.validate_min_interval(cron_expression):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Cron expression fires too frequently. Minimum interval is 15 minutes.",
                )

        if st == ScheduleType.ONE_SHOT.value:
            if not run_at:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="run_at is required for ONE_SHOT jobs",
                )
            now = datetime.now(timezone.utc)
            run_at_aware = run_at if run_at.tzinfo else run_at.replace(tzinfo=timezone.utc)
            if run_at_aware <= now:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="run_at must be in the future for ONE_SHOT jobs",
                )

    @staticmethod
    def _validate_job_config(agent_type: str, config: dict) -> None:
        at = agent_type.value if hasattr(agent_type, "value") else agent_type

        if at == AgentType.CRAWL.value:
            if not config.get("target_url"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="job_config.target_url is required for CRAWL jobs",
                )

        if at == AgentType.GENERATION.value:
            if not config.get("requirement_ids") and not config.get("auto_generate"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "GENERATION jobs require job_config.requirement_ids "
                        "or job_config.auto_generate=true"
                    ),
                )

        if at == AgentType.EXECUTION.value:
            has_ids = bool(config.get("script_ids") or config.get("script_id"))
            if not has_ids and not config.get("auto_execute_approved"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "EXECUTION jobs require job_config.script_ids "
                        "or job_config.auto_execute_approved=true"
                    ),
                )

    @staticmethod
    def _calculate_next_run(
        schedule_type: str,
        cron_expression: str | None,
        run_at: datetime | None,
        timezone_str: str = "UTC",
    ) -> datetime | None:
        st = schedule_type.value if hasattr(schedule_type, "value") else schedule_type
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if st == ScheduleType.RECURRING.value and cron_expression:
            return compute_next_run(cron_expression, timezone_str or "UTC", now)
        if st == ScheduleType.ONE_SHOT.value and run_at:
            return run_at.replace(tzinfo=None) if run_at.tzinfo else run_at
        return None
