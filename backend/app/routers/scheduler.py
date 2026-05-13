from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_manage_content, can_run_agents
from app.dependencies import get_db, get_current_user_id
from app.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobRead,
    ScheduledJobRunRead,
    ScheduledJobUpdate,
)
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scheduled_jobs", tags=["scheduler"])


@router.get("", response_model=list[ScheduledJobRead], dependencies=[any_authenticated])
async def list_jobs(db: AsyncSession = Depends(get_db)) -> list[ScheduledJobRead]:
    return await SchedulerService(db).list_jobs()


@router.post("", response_model=ScheduledJobRead, status_code=201, dependencies=[can_manage_content])
async def create_job(
    body: ScheduledJobCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> ScheduledJobRead:
    created_by = get_current_user_id(request)
    return await SchedulerService(db).create_job(body, created_by=created_by)


@router.get("/{job_id}", response_model=ScheduledJobRead, dependencies=[any_authenticated])
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)) -> ScheduledJobRead:
    return await SchedulerService(db).get_job(job_id)


@router.put("/{job_id}", response_model=ScheduledJobRead, dependencies=[can_manage_content])
async def update_job(
    job_id: UUID, body: ScheduledJobUpdate, db: AsyncSession = Depends(get_db)
) -> ScheduledJobRead:
    return await SchedulerService(db).update_job(job_id, body)


@router.delete("/{job_id}", status_code=204, dependencies=[can_manage_content])
async def delete_job(job_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await SchedulerService(db).delete_job(job_id)


@router.post("/{job_id}/trigger", response_model=ScheduledJobRunRead, status_code=202, dependencies=[can_run_agents])
async def trigger_job(job_id: UUID, db: AsyncSession = Depends(get_db)) -> ScheduledJobRunRead:
    return await SchedulerService(db).trigger_now(job_id)


@router.get("/{job_id}/runs", response_model=list[ScheduledJobRunRead], dependencies=[any_authenticated])
async def list_job_runs(job_id: UUID, db: AsyncSession = Depends(get_db)) -> list[ScheduledJobRunRead]:
    return await SchedulerService(db).list_runs(job_id)
