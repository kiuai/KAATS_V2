from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import any_authenticated, can_manage_content, can_run_agents
from app.dependencies import get_db
from app.schemas.test_script import TestScriptCreate, TestScriptRead, TestScriptUpdate
from app.services.test_script_service import TestScriptService

router = APIRouter(tags=["test_scripts"])


@router.get("/systems/{system_id}/scripts", response_model=list[TestScriptRead], dependencies=[any_authenticated])
async def list_scripts(system_id: UUID, db: AsyncSession = Depends(get_db)) -> list[TestScriptRead]:
    return await TestScriptService(db).list_for_system(system_id)


@router.post("/systems/{system_id}/scripts", response_model=TestScriptRead, status_code=201, dependencies=[can_run_agents])
async def create_script(
    system_id: UUID, body: TestScriptCreate, db: AsyncSession = Depends(get_db)
) -> TestScriptRead:
    return await TestScriptService(db).create(system_id, body)


@router.get("/scripts/{script_id}", response_model=TestScriptRead, dependencies=[any_authenticated])
async def get_script(script_id: UUID, db: AsyncSession = Depends(get_db)) -> TestScriptRead:
    return await TestScriptService(db).get(script_id)


@router.put("/scripts/{script_id}", response_model=TestScriptRead, dependencies=[can_run_agents])
async def update_script(
    script_id: UUID, body: TestScriptUpdate, db: AsyncSession = Depends(get_db)
) -> TestScriptRead:
    return await TestScriptService(db).update(script_id, body)


@router.delete("/scripts/{script_id}", status_code=204, response_model=None, dependencies=[can_manage_content])
async def delete_script(script_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await TestScriptService(db).delete(script_id)


@router.get("/scripts/{script_id}/export/{format}", dependencies=[any_authenticated])
async def export_script(
    script_id: UUID, format: str, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    content, media_type, filename = await TestScriptService(db).export(script_id, format)
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
