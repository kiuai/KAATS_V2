"""
Dispatch a ScheduledJob: resolve auto-expand config, call AgentDispatcher,
create ScheduledJobRun, and record the trigger on the job record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AgentType, ScheduleType
from app.models.scheduled_job import ScheduledJob, ScheduledJobRun

log = structlog.get_logger(__name__)


async def dispatch_scheduled_job(db: AsyncSession, job: ScheduledJob) -> ScheduledJobRun:
    """
    Main entry point called by the evaluator for each due ScheduledJob.

    1. Resolve final job_config (expand auto_generate / auto_execute_approved)
    2. Call AgentDispatcher.dispatch_* → creates AgentRun + publishes to Service Bus
    3. Create ScheduledJobRun record
    4. Update job (last_run_at, next_run_at / is_active)
    Returns the ScheduledJobRun record.
    """
    from app.services.agent_dispatcher import AgentDispatcher

    now_utc = datetime.now(UTC).replace(tzinfo=None)
    resolved_config = await _resolve_config(db, job)

    dispatcher = AgentDispatcher(db)
    agent_run = await _dispatch_for_type(dispatcher, job, resolved_config)

    # Create run record
    run = ScheduledJobRun(
        job_id=job.id,
        agent_run_id=agent_run.id,
        status="triggered",
        scheduled_for=now_utc,
    )
    db.add(run)

    # Update job state
    job.last_run_at = now_utc
    job.last_run_status = "pending"

    if job.schedule_type == ScheduleType.ONE_SHOT.value:
        job.is_active = False
        log.info("scheduler.one_shot.completed", job_id=str(job.id))
    else:
        from app.scheduler.cron_parser import compute_next_run

        tz = job.timezone or "UTC"
        job.next_run_at = compute_next_run(job.cron_expression or "0 0 * * *", tz, now_utc)

    await db.flush()
    log.info(
        "scheduler.job_dispatched",
        job_id=str(job.id),
        job_name=job.name,
        agent_type=job.agent_type,
        agent_run_id=str(agent_run.id),
        schedule_run_id=str(run.id),
    )
    return run


async def _dispatch_for_type(
    dispatcher: AgentDispatcher,
    job: ScheduledJob,
    config: dict,
) -> AgentRun:
    """Route to the correct AgentDispatcher method based on agent_type."""

    company_id: UUID = job.company_id
    system_id: UUID | None = job.system_id

    if job.agent_type == AgentType.CRAWL.value:
        return await dispatcher.dispatch_crawl(
            company_id=company_id,
            system_id=system_id,  # type: ignore[arg-type]
            base_url=config.get("target_url", config.get("base_url", "")),
            triggered_by_user_id=job.created_by,
            scheduled_job_id=job.id,
            max_pages=config.get("max_pages"),
        )

    if job.agent_type == AgentType.GENERATION.value:
        req_ids = [UUID(r) for r in config.get("requirement_ids", []) if r]
        return await dispatcher.dispatch_generation(
            company_id=company_id,
            system_id=system_id,  # type: ignore[arg-type]
            requirement_ids=req_ids,
            target_formats=config.get("target_formats") or config.get("export_formats"),
            triggered_by_user_id=job.created_by,
            scheduled_job_id=job.id,
        )

    if job.agent_type == AgentType.EXECUTION.value:
        script_ids = config.get("script_ids", [])
        if script_ids:
            # Dispatch one run per script
            last_run = None
            for sid in script_ids:
                last_run = await dispatcher.dispatch_execution(
                    company_id=company_id,
                    system_id=system_id,  # type: ignore[arg-type]
                    script_id=UUID(sid),
                    triggered_by_user_id=job.created_by,
                    scheduled_job_id=job.id,
                )
            return last_run  # type: ignore[return-value]
        # Fallback: single script_id
        return await dispatcher.dispatch_execution(
            company_id=company_id,
            system_id=system_id,  # type: ignore[arg-type]
            script_id=UUID(config["script_id"]),
            triggered_by_user_id=job.created_by,
            scheduled_job_id=job.id,
        )

    raise ValueError(f"Unknown agent_type: {job.agent_type!r}")


async def _resolve_config(db: AsyncSession, job: ScheduledJob) -> dict:
    """
    Expand auto_generate / auto_execute_approved flags into concrete IDs.
    Returns the effective config dict.
    """
    config: dict = dict(job.job_config or {})

    if not job.system_id:
        return config

    if job.agent_type == AgentType.GENERATION.value and config.get("auto_generate"):
        config["requirement_ids"] = await _active_requirements_without_scripts(db, job.system_id)
        log.info(
            "scheduler.auto_generate.expanded",
            job_id=str(job.id),
            requirement_count=len(config["requirement_ids"]),
        )

    if job.agent_type == AgentType.EXECUTION.value and config.get("auto_execute_approved"):
        config["script_ids"] = await _approved_scripts_not_recently_run(db, job.system_id)
        log.info(
            "scheduler.auto_execute.expanded",
            job_id=str(job.id),
            script_count=len(config["script_ids"]),
        )

    return config


async def _active_requirements_without_scripts(db: AsyncSession, system_id: UUID) -> list[str]:
    """
    Return IDs of ACTIVE requirements in the system that have no APPROVED test script.
    """
    from sqlalchemy import exists, select

    from app.models.enums import RequirementStatus, TestScriptStatus
    from app.models.requirement import Requirement
    from app.models.test_script import TestScript

    approved_sub = (
        select(TestScript.requirement_id)
        .where(
            TestScript.requirement_id == Requirement.id,
            TestScript.status == TestScriptStatus.APPROVED.value,
        )
        .correlate(Requirement)
    )

    result = await db.execute(
        select(Requirement.id).where(
            Requirement.system_id == system_id,
            Requirement.status == RequirementStatus.ACTIVE.value,
            ~exists(approved_sub),
        )
    )
    return [str(r) for r in result.scalars().all()]


async def _approved_scripts_not_recently_run(db: AsyncSession, system_id: UUID) -> list[str]:
    """
    Return IDs of APPROVED scripts in the system that have not been executed
    in the last 24 hours.
    """
    from datetime import timedelta

    from sqlalchemy import exists, select

    from app.models.enums import TestScriptStatus
    from app.models.execution_evidence import ExecutionRun
    from app.models.test_script import TestScript

    cutoff = (datetime.now(UTC) - timedelta(hours=24)).replace(tzinfo=None)

    recent_sub = (
        select(ExecutionRun.test_script_id)
        .where(
            ExecutionRun.test_script_id == TestScript.id,
            ExecutionRun.created_at > cutoff,
        )
        .correlate(TestScript)
    )

    result = await db.execute(
        select(TestScript.id).where(
            TestScript.system_id == system_id,
            TestScript.status == TestScriptStatus.APPROVED.value,
            ~exists(recent_sub),
        )
    )
    return [str(s) for s in result.scalars().all()]


# ── Backwards-compatible shim ─────────────────────────────────────────────────


async def dispatch_job(db: AsyncSession, job: ScheduledJob) -> ScheduledJobRun:
    """Legacy alias used by the manual trigger endpoint."""
    return await dispatch_scheduled_job(db, job)
