from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session_factory
import app.models.agent_run  # noqa: F401 — registers AgentRun in mapper registry
from app.models.scheduled_job import ScheduledJob
from app.scheduler.cron_parser import compute_next_run
from app.scheduler.job_dispatcher import dispatch_job

log = structlog.get_logger(__name__)


async def scheduler_loop() -> None:
    """Main scheduler loop. Runs indefinitely, evaluating due jobs every interval."""
    settings = get_settings()
    log.info("scheduler.loop.started", interval_seconds=settings.scheduler_interval_seconds)
    while True:
        try:
            await _evaluate_due_jobs()
        except Exception:
            log.exception("scheduler.evaluation.error")
        await asyncio.sleep(settings.scheduler_interval_seconds)


async def _evaluate_due_jobs() -> None:
    settings = get_settings()
    factory = get_session_factory()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    async with factory() as db:
        async with db.begin():
            result = await db.execute(
                select(ScheduledJob)
                .where(
                    ScheduledJob.is_active == True,  # noqa: E712
                    ScheduledJob.next_run_at <= now,
                )
                .order_by(ScheduledJob.next_run_at.asc())
                .limit(settings.scheduler_max_jobs_per_cycle)
                .with_for_update(skip_locked=True)
            )
            due_jobs = result.scalars().all()

            if not due_jobs:
                return

            log.info("scheduler.evaluation.due_jobs_found", count=len(due_jobs))
            for job in due_jobs:
                next_run = compute_next_run(job.cron_expression, job.timezone, now)
                job.next_run_at = next_run
                job.last_run_at = now
                await dispatch_job(db, job)


async def handle_job_completion(
    db: AsyncSession,
    job_id: str,
    run_id: str,
    success: bool,
    failure_reason: str | None = None,
) -> None:
    """
    Called by the Worker after an agent run completes.
    Updates consecutive_failures and auto-disables if threshold is reached.
    """
    from app.models.scheduled_job import ScheduledJobRun

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    run = await db.get(ScheduledJobRun, run_id)
    if run:
        run.status = "completed" if success else "failed"
        run.completed_at = now
        run.failure_reason = failure_reason

    job = await db.get(ScheduledJob, job_id)
    if not job:
        return

    if success:
        job.consecutive_failures = 0
    else:
        job.consecutive_failures += 1
        if job.consecutive_failures >= job.max_failures:
            job.is_active = False
            log.warning(
                "scheduler.job.auto_disabled",
                job_id=job_id,
                consecutive_failures=job.consecutive_failures,
            )

    await db.flush()
