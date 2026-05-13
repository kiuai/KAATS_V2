from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_manage_content, can_run_agents
from app.dependencies import get_db
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementUpdate
from app.services.requirement_service import RequirementService

router = APIRouter(tags=["requirements"])


@router.get("/systems/{system_id}/requirements", response_model=list[RequirementRead], dependencies=[any_authenticated])
async def list_requirements(system_id: UUID, db: AsyncSession = Depends(get_db)) -> list[RequirementRead]:
    return await RequirementService(db).list_for_system(system_id)


@router.post("/systems/{system_id}/requirements", response_model=RequirementRead, status_code=201, dependencies=[can_run_agents])
async def create_requirement(
    system_id: UUID, body: RequirementCreate, db: AsyncSession = Depends(get_db)
) -> RequirementRead:
    return await RequirementService(db).create(system_id, body)


@router.get("/requirements/{requirement_id}", response_model=RequirementRead, dependencies=[any_authenticated])
async def get_requirement(requirement_id: UUID, db: AsyncSession = Depends(get_db)) -> RequirementRead:
    return await RequirementService(db).get(requirement_id)


@router.put("/requirements/{requirement_id}", response_model=RequirementRead, dependencies=[can_run_agents])
async def update_requirement(
    requirement_id: UUID, body: RequirementUpdate, db: AsyncSession = Depends(get_db)
) -> RequirementRead:
    return await RequirementService(db).update(requirement_id, body)


@router.delete("/requirements/{requirement_id}", status_code=204, response_model=None, dependencies=[can_manage_content])
async def delete_requirement(requirement_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await RequirementService(db).delete(requirement_id)


@router.post("/requirements/{requirement_id}/approve", response_model=RequirementRead, dependencies=[can_manage_content])
async def approve_requirement(requirement_id: UUID, db: AsyncSession = Depends(get_db)) -> RequirementRead:
    return await RequirementService(db).approve(requirement_id)
