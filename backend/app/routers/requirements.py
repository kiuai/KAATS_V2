"""Requirements router — paginated list, import two-phase, quality-check, generate-script."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import (
    Permission,
    any_authenticated,
    can_manage_content,
    can_run_agents,
    require_system_access,
)
from app.dependencies import get_db, get_current_user_id, get_current_company_id
from app.models.enums import UserRoleEnum
from app.schemas.common import Page
from app.schemas.requirement import (
    GenerateScriptBody,
    QualityCheckResult,
    RequirementCreate,
    RequirementImportConfirm,
    RequirementImportPreview,
    RequirementRead,
    RequirementUpdate,
    RequirementWithScripts,
)
from app.services.requirement_service import RequirementService, parse_requirement_file

router = APIRouter(tags=["requirements"])


def _get_bpo_domain(current_user: CurrentUser) -> str | None:
    """Return business_domain if caller is a BPO-only user, else None."""
    roles = {r.role for r in current_user.roles}
    non_bpo = {
        UserRoleEnum.GLOBAL_ADMIN.value,
        UserRoleEnum.ENTERPRISE_ADMIN.value,
        UserRoleEnum.COMPANY_ADMIN.value,
        UserRoleEnum.SYSTEM_MANAGER.value,
        UserRoleEnum.VALIDATION_LEAD.value,
        UserRoleEnum.QA.value,
        UserRoleEnum.VALIDATION_TESTER.value,
    }
    if UserRoleEnum.BPO.value in roles and not roles.intersection(non_bpo):
        for r in current_user.roles:
            if r.role == UserRoleEnum.BPO.value and r.business_domain:
                return r.business_domain
    return None


# ── System-scoped list / create ───────────────────────────────────────────────

@router.get("/systems/{system_id}/requirements", response_model=Page[RequirementRead])
async def list_requirements(
    system_id: UUID,
    request: Request,
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    business_domain: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: object = require_system_access(Permission.REQ_READ),
) -> Page[RequirementRead]:
    bpo_domain = _get_bpo_domain(current_user)
    return await RequirementService(db).list_for_system_paginated(
        system_id=system_id,
        bpo_domain=bpo_domain,
        status_filter=status,
        priority=priority,
        business_domain=business_domain,
        source_type=source_type,
        search=search,
        limit=limit,
        offset=offset,
        cursor=cursor,
    )


@router.post("/systems/{system_id}/requirements", response_model=RequirementRead, status_code=201)
async def create_requirement(
    system_id: UUID,
    body: RequirementCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.REQ_CREATE),
) -> RequirementRead:
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await RequirementService(db).create_with_context(
        system_id=system_id,
        body=body,
        company_id=company_id,
        created_by=user_id,
    )


# ── Import two-phase ──────────────────────────────────────────────────────────

@router.post("/systems/{system_id}/requirements/import/preview", response_model=list[RequirementImportPreview])
async def import_preview(
    system_id: UUID,
    file: UploadFile = File(...),
    _: object = require_system_access(Permission.REQ_IMPORT),
) -> list[RequirementImportPreview]:
    content = await file.read()
    filename = file.filename or "upload.txt"
    return parse_requirement_file(filename, content)


@router.post("/systems/{system_id}/requirements/import/confirm", response_model=list[RequirementRead], status_code=201)
async def import_confirm(
    system_id: UUID,
    body: RequirementImportConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: object = require_system_access(Permission.REQ_IMPORT),
) -> list[RequirementRead]:
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await RequirementService(db).bulk_create(
        system_id=system_id,
        previews=body.requirements,
        company_id=company_id,
        created_by=user_id,
        source_reference=body.source_reference,
        default_domain=body.business_domain,
    )


# ── Requirement CRUD ──────────────────────────────────────────────────────────

@router.get("/requirements/{requirement_id}", response_model=RequirementWithScripts)
async def get_requirement(
    requirement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementWithScripts:
    # Basic authentication only; system check happens via company scoping in service
    return await RequirementService(db).get_with_scripts(requirement_id)


@router.patch("/requirements/{requirement_id}", response_model=RequirementRead)
async def update_requirement(
    requirement_id: UUID,
    body: RequirementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementRead:
    return await RequirementService(db).update(requirement_id, body)


@router.put("/requirements/{requirement_id}", response_model=RequirementRead, include_in_schema=False)
async def update_requirement_put(
    requirement_id: UUID,
    body: RequirementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementRead:
    return await RequirementService(db).update(requirement_id, body)


@router.delete("/requirements/{requirement_id}", status_code=204, response_model=None)
async def delete_requirement(
    requirement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    await RequirementService(db).soft_delete(requirement_id)


@router.post("/requirements/{requirement_id}/approve", response_model=RequirementRead, dependencies=[can_manage_content])
async def approve_requirement(
    requirement_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RequirementRead:
    return await RequirementService(db).approve(requirement_id)


# ── Quality check ─────────────────────────────────────────────────────────────

@router.get("/requirements/{requirement_id}/quality-check", response_model=QualityCheckResult)
async def quality_check(
    requirement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> QualityCheckResult:
    return await RequirementService(db).quality_check(requirement_id)


# ── Generate script ───────────────────────────────────────────────────────────

@router.post("/requirements/{requirement_id}/generate-script")
async def generate_script(
    requirement_id: UUID,
    body: GenerateScriptBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    user_id = get_current_user_id(request)
    company_id = get_current_company_id(request)
    return await RequirementService(db).generate_script(
        requirement_id=requirement_id,
        export_format=body.export_format,
        company_id=company_id,
        triggered_by_user_id=user_id,
    )


# ── Bulk operations ───────────────────────────────────────────────────────────


class BulkDeleteBody(BaseModel):
    ids: list[UUID]


class BulkDeleteResult(BaseModel):
    deleted: int
    errors: list[str]


@router.post(
    "/systems/{system_id}/requirements/bulk-delete",
    response_model=BulkDeleteResult,
    status_code=status.HTTP_200_OK,
    dependencies=[can_manage_content],
    summary="Soft-delete multiple requirements",
)
async def bulk_delete_requirements(
    system_id: UUID,
    body: BulkDeleteBody,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BulkDeleteResult:
    if not body.ids:
        raise HTTPException(status_code=422, detail="ids must not be empty")
    svc = RequirementService(db)
    deleted = 0
    errors: list[str] = []
    for req_id in body.ids:
        try:
            await svc.soft_delete(req_id)
            deleted += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{req_id}: {exc}")
    await db.commit()
    return BulkDeleteResult(deleted=deleted, errors=errors)
