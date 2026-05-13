"""Schedule evaluator — queries due jobs and dispatches them via AgentDispatcher."""
from __future__ import annotations

import asyncio
import signal
from datetime import datetime, timezone
from time import perf_counter

import structlog

from app.config import get_settings
from app.database import get_session_factory

log = structlog.get_logger(__name__)


class ScheduleEvaluator:
    """
    Polls the database for due ScheduledJobs and dispatches them.
    Designed to run in the scheduler container; called every
    ``SCHEDULER_INTERVAL_SECONDS`` (default: 60 s).
    """

    def __init__(self) -> None:
        self._running = True

    async def run_once(self) -> None:
        """
        Single evaluation pass — queries due jobs and dispatches each one.
        Called by start() and also directly in tests.
        """
        from sqlalchemy import select
        from app.models.scheduled_job import ScheduledJob
        from app.scheduler.job_dispatcher import dispatch_scheduled_job

        settings = get_settings()
        t0 = perf_counter()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        jobs_triggered = 0

        factory = get_session_factory()
        async with factory() as db:
            try:
                async with db.begin():
                    # Fetch jobs that are due and not already running.
                    # `with_for_update(skip_locked=True)` prevents double-firing
                    # when multiple scheduler replicas run concurrently.
                    result = await db.execute(
                        select(ScheduledJob)
                        .where(
                            ScheduledJob.is_active == True,  # noqa: E712
                            ScheduledJob.next_run_at <= now,
                            # Guard: don't re-fire a job within the same window
                            (ScheduledJob.last_run_at.is_(None))
                            | (ScheduledJob.last_run_at < ScheduledJob.next_run_at),
                        )
                        .order_by(ScheduledJob.next_run_at.asc())
                        .limit(settings.scheduler_max_jobs_per_cycle)
                        .with_for_update(skip_locked=True)
                    )
                    due_jobs = result.scalars().all()

                    for job in due_jobs:
                        try:
                            run = await dispatch_scheduled_job(db, job)
                            jobs_triggered += 1
                            log.info(
                                "scheduler.job_triggered",
                                job_id=str(job.id),
                                job_name=job.name,
                                agent_type=job.agent_type,
                                system_id=str(job.system_id),
                                schedule_run_id=str(run.id),
                            )
                        except Exception as exc:
                            log.error(
                                "scheduler.job_dispatch_failed",
                                job_id=str(job.id),
                                job_name=job.name,
                                error=str(exc),
                            )
                            # Increment failure counter
                            job.consecutive_failures = (job.consecutive_failures or 0) + 1
                            if job.consecutive_failures >= job.max_failures:
                                job.is_active = False
                                log.warning(
                                    "scheduler.job_auto_disabled",
                                    job_id=str(job.id),
                                    consecutive_failures=job.consecutive_failures,
                                )
            except Exception as exc:
                log.exception("scheduler.evaluation_failed", error=str(exc))
                raise

        duration_ms = round((perf_counter() - t0) * 1000)
        log.info(
            "scheduler.evaluation_complete",
            jobs_evaluated=len(due_jobs) if "due_jobs" in dir() else 0,
            jobs_triggered=jobs_triggered,
            duration_ms=duration_ms,
        )

    async def start(self) -> None:
        """
        Run indefinitely, calling run_once() every SCHEDULER_INTERVAL_SECONDS.
        Handles SIGTERM / SIGINT for graceful shutdown.
        """
        settings = get_settings()
        interval = settings.scheduler_interval_seconds

        self._setup_signal_handlers()

        log.info("scheduler.evaluator.started", interval_seconds=interval)

        while self._running:
            try:
                await self.run_once()
            except Exception:
                log.exception("scheduler.run_once.unhandled_error")

            if not self._running:
                break

            # Sleep in small increments so SIGTERM is handled promptly
            slept = 0.0
            while slept < interval and self._running:
                await asyncio.sleep(min(1.0, interval - slept))
                slept += 1.0

        log.info("scheduler.evaluator.stopped")

    def stop(self) -> None:
        """Signal the evaluation loop to exit after the current pass."""
        self._running = False
        log.info("scheduler.evaluator.stop_requested")

    def _setup_signal_handlers(self) -> None:
        loop = asyncio.get_event_loop()

        def _handle_signal(sig: signal.Signals) -> None:
            log.info("scheduler.signal_received", signal=sig.name)
            self.stop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _handle_signal, sig)
            except (NotImplementedError, RuntimeError):
                # Windows / restricted environments don't support add_signal_handler
                pass


# ── Module-level helper (backwards compat with Dockerfile.scheduler CMD) ─────

async def scheduler_loop() -> None:
    """Entry point called by Dockerfile.scheduler CMD."""
    await ScheduleEvaluator().start()
