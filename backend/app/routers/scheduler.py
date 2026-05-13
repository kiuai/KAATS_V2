from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import (
    Permission,
    any_authenticated,
    require_system_access,
)
from app.dependencies import get_db, get_current_user_id, get_current_company_id
from app.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobRead,
    ScheduledJobRunRead,
    ScheduledJobUpdate,
)
from app.services.scheduler_service import SchedulerService

router = APIRouter(tags=["scheduler"])


# ── List jobs for a system ────────────────────────────────────────────────────

@router.get(
    "/systems/{system_id}/schedules",
    response_model=list[ScheduledJobRead],
    dependencies=[Depends(require_system_access(Permission.SCHEDULE_READ))],
)
async def list_schedules(
    system_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledJobRead]:
    """List all scheduled jobs for a system."""
    company_id = get_current_company_id(request)
    return await SchedulerService(db).list_scheduled_jobs(system_id, company_id)


# ── Create a scheduled job ────────────────────────────────────────────────────

@router.post(
    "/systems/{system_id}/schedules",
    response_model=ScheduledJobRead,
    status_code=201,
    dependencies=[Depends(require_system_access(Permission.SCHEDULE_CREATE))],
)
async def create_schedule(
    system_id: UUID,
    body: ScheduledJobCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRead:
    """Create a new scheduled job for a system."""
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await SchedulerService(db).create_scheduled_job(
        body=body,
        system_id=system_id,
        created_by=user_id,
        company_id=company_id,
    )


# ── Get a single scheduled job ────────────────────────────────────────────────

@router.get(
    "/systems/{system_id}/schedules/{job_id}",
    response_model=ScheduledJobRead,
    dependencies=[Depends(require_system_access(Permission.SCHEDULE_READ))],
)
async def get_schedule(
    system_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRead:
    """Get a scheduled job by ID."""
    return await SchedulerService(db).get_scheduled_job(job_id, system_id)


# ── Update a scheduled job ────────────────────────────────────────────────────

@router.patch(
    "/systems/{system_id}/schedules/{job_id}",
    response_model=ScheduledJobRead,
    dependencies=[Depends(require_system_access(Permission.SCHEDULE_UPDATE))],
)
async def update_schedule(
    system_id: UUID,
    job_id: UUID,
    body: ScheduledJobUpdate,
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRead:
    """Update name, schedule, job_config, or is_active flag."""
    return await SchedulerService(db).update_scheduled_job(job_id, system_id, body)


# ── Deactivate (soft-delete) a scheduled job ──────────────────────────────────

@router.delete(
    "/systems/{system_id}/schedules/{job_id}",
    response_model=ScheduledJobRead,
    dependencies=[Depends(require_system_access(Permission.SCHEDULE_DELETE))],
)
async def deactivate_schedule(
    system_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRead:
    """Deactivate a scheduled job (soft delete — sets is_active=False)."""
    return await SchedulerService(db).deactivate_scheduled_job(job_id, system_id)


# ── Run history ───────────────────────────────────────────────────────────────

@router.get(
    "/systems/{system_id}/schedules/{job_id}/runs",
    response_model=list[ScheduledJobRunRead],
    dependencies=[Depends(require_system_access(Permission.SCHEDULE_READ))],
)
async def list_schedule_runs(
    system_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledJobRunRead]:
    """List ScheduledJobRun history for a job (most recent first, max 100)."""
    return await SchedulerService(db).list_job_runs(job_id, system_id)


# ── Manual trigger ────────────────────────────────────────────────────────────

@router.post(
    "/systems/{system_id}/schedules/{job_id}/trigger-now",
    response_model=ScheduledJobRunRead,
    status_code=202,
    dependencies=[Depends(require_system_access(Permission.SCHEDULE_UPDATE))],
)
async def trigger_schedule_now(
    system_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ScheduledJobRunRead:
    """Manually trigger a scheduled job immediately (for testing the schedule)."""
    return await SchedulerService(db).trigger_now(job_id, system_id)


# ── Legacy routes (old /scheduled_jobs prefix, kept for backwards compat) ─────

@router.get("/scheduled_jobs", response_model=list[ScheduledJobRead], dependencies=[any_authenticated], include_in_schema=False)
async def list_jobs_legacy(db: AsyncSession = Depends(get_db)) -> list[ScheduledJobRead]:
    return await SchedulerService(db).list_jobs()


@router.get("/scheduled_jobs/{job_id}", response_model=ScheduledJobRead, dependencies=[any_authenticated], include_in_schema=False)
async def get_job_legacy(job_id: UUID, db: AsyncSession = Depends(get_db)) -> ScheduledJobRead:
    return await SchedulerService(db).get_job(job_id)


@router.get("/scheduled_jobs/{job_id}/runs", response_model=list[ScheduledJobRunRead], dependencies=[any_authenticated], include_in_schema=False)
async def list_runs_legacy(job_id: UUID, db: AsyncSession = Depends(get_db)) -> list[ScheduledJobRunRead]:
    return await SchedulerService(db).list_runs(job_id)
