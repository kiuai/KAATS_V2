"""
Test Scripts router — system-scoped CRUD, status workflow, versioning, export.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user, get_tenant_context
from app.auth.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    any_authenticated,
    can_manage_content,
    require_system_access,
)
from app.dependencies import get_db
from app.models.enums import UserRoleEnum
from app.schemas.test_script import (
    BulkExportRequest,
    BulkExportResultRead,
    TestScriptCreate,
    TestScriptRead,
    TestScriptRejectBody,
    TestScriptUpdate,
    TestScriptVersionRead,
)
from app.services.test_script_service import TestScriptService

router = APIRouter(tags=["test_scripts"])


# ── System-scoped list / create ───────────────────────────────────────────────


@router.get(
    "/systems/{system_id}/test-scripts",
    response_model=list[TestScriptRead],
)
async def list_scripts(
    system_id: UUID,
    status: str | None = Query(default=None),
    format: str | None = Query(default=None),
    business_domain: str | None = Query(default=None),
    ai_generated: bool | None = Query(default=None),
    requirement_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _system=require_system_access(Permission.SCRIPT_READ),
) -> list[TestScriptRead]:
    """List test scripts with optional filters.
    BPO users are automatically restricted to their assigned business_domain."""
    bpo_domain = _get_bpo_domain(current_user)
    return await TestScriptService(db).list_for_system_filtered(
        system_id=system_id,
        status_filter=status,
        export_format=format,
        business_domain=business_domain,
        ai_generated=ai_generated,
        requirement_id=requirement_id,
        search=search,
        bpo_domain=bpo_domain,
    )


@router.post(
    "/systems/{system_id}/test-scripts",
    response_model=TestScriptRead,
    status_code=201,
)
async def create_script(
    system_id: UUID,
    body: TestScriptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    company=Depends(get_tenant_context),
    _system=require_system_access(Permission.SCRIPT_CREATE),
) -> TestScriptRead:
    """Manually create a test script."""
    return await TestScriptService(db).create_with_context(
        system_id=system_id,
        body=body,
        company_id=company.id,
        created_by=current_user.user.id,
    )


# ── Script detail / update / delete ──────────────────────────────────────────


@router.get(
    "/test-scripts/{script_id}",
    response_model=TestScriptRead,
    dependencies=[any_authenticated],
)
async def get_script(
    script_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TestScriptRead:
    """Return full script detail including version list."""
    return await TestScriptService(db).get_with_versions(script_id)


@router.patch(
    "/test-scripts/{script_id}",
    response_model=TestScriptRead,
)
async def update_script(
    script_id: UUID,
    body: TestScriptUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm=any_authenticated,
) -> TestScriptRead:
    """Update a script. Auto-creates a version record for audit trail."""
    return await TestScriptService(db).update_with_version(
        script_id=script_id,
        body=body,
        updated_by=current_user.user.id,
    )


@router.delete(
    "/test-scripts/{script_id}",
    status_code=204,
    response_model=None,
    dependencies=[can_manage_content],
)
async def delete_script(
    script_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a test script."""
    await TestScriptService(db).soft_delete(script_id)


# ── Status workflow ───────────────────────────────────────────────────────────


@router.post(
    "/test-scripts/{script_id}/submit-for-review",
    response_model=TestScriptRead,
    dependencies=[any_authenticated],
)
async def submit_for_review(
    script_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TestScriptRead:
    """Transition a DRAFT script to IN_REVIEW."""
    return await TestScriptService(db).submit_for_review(script_id)


@router.post(
    "/test-scripts/{script_id}/approve",
    response_model=TestScriptRead,
)
async def approve_script(
    script_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm=any_authenticated,
) -> TestScriptRead:
    """Approve a script (requires SCRIPT_APPROVE permission)."""
    _check_permission(current_user, Permission.SCRIPT_APPROVE)
    return await TestScriptService(db).approve(script_id, approver_id=current_user.user.id)


@router.post(
    "/test-scripts/{script_id}/reject",
    response_model=TestScriptRead,
)
async def reject_script(
    script_id: UUID,
    body: TestScriptRejectBody,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _perm=any_authenticated,
) -> TestScriptRead:
    """Reject a script back to DRAFT with a mandatory comment."""
    _check_permission(current_user, Permission.SCRIPT_APPROVE)
    return await TestScriptService(db).reject(
        script_id,
        rejection_comment=body.rejection_comment,
        rejected_by=current_user.user.id,
    )


# ── Version history ───────────────────────────────────────────────────────────


@router.get(
    "/test-scripts/{script_id}/versions",
    response_model=list[TestScriptVersionRead],
    dependencies=[any_authenticated],
)
async def list_versions(
    script_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[TestScriptVersionRead]:
    """Return all version records for a script, newest first."""
    return await TestScriptService(db).get_versions(script_id)


@router.get(
    "/test-scripts/{script_id}/versions/{version}",
    response_model=TestScriptVersionRead,
    dependencies=[any_authenticated],
)
async def get_version(
    script_id: UUID,
    version: int,
    db: AsyncSession = Depends(get_db),
) -> TestScriptVersionRead:
    """Return a specific version of a script."""
    return await TestScriptService(db).get_version(script_id, version)


# ── Export ────────────────────────────────────────────────────────────────────


@router.get(
    "/test-scripts/{script_id}/export",
    response_class=RedirectResponse,
    status_code=302,
)
async def export_script(
    script_id: UUID,
    format: str = Query(default="playwright"),
    db: AsyncSession = Depends(get_db),
    company=Depends(get_tenant_context),
    _perm=any_authenticated,
) -> RedirectResponse:
    """Export a single script. Redirects to a 1-hour SAS download URL."""
    from app.services.export_service import ExportService

    result = await ExportService(db).export_script(
        script_id=script_id,
        export_format=format,
        company_id=company.id,
    )
    return RedirectResponse(url=result.sas_url, status_code=302)


@router.post(
    "/test-scripts/export-bulk",
    response_model=BulkExportResultRead,
)
async def export_bulk(
    body: BulkExportRequest,
    db: AsyncSession = Depends(get_db),
    company=Depends(get_tenant_context),
    _perm=any_authenticated,
) -> BulkExportResultRead:
    """Export multiple scripts as a ZIP archive. Returns a 1-hour SAS URL."""
    from app.services.export_service import ExportService

    result = await ExportService(db).export_bulk(
        script_ids=body.script_ids,
        export_format=body.format,
        company_id=company.id,
    )
    return BulkExportResultRead(
        sas_url=result.sas_url,
        filename=result.filename,
        script_count=result.script_count,
    )


@router.get(
    "/test-cycles/{cycle_id}/export",
    response_class=RedirectResponse,
    status_code=302,
)
async def export_cycle(
    cycle_id: UUID,
    format: str = Query(default="playwright"),
    db: AsyncSession = Depends(get_db),
    company=Depends(get_tenant_context),
    _perm=any_authenticated,
) -> RedirectResponse:
    """Export all APPROVED scripts in a test cycle as a ZIP. Redirects to SAS URL."""
    from app.services.export_service import ExportService

    result = await ExportService(db).export_cycle(
        cycle_id=cycle_id,
        export_format=format,
        company_id=company.id,
    )
    return RedirectResponse(url=result.sas_url, status_code=302)


# ── Legacy routes (backwards compatibility) ───────────────────────────────────


@router.get(
    "/systems/{system_id}/scripts",
    response_model=list[TestScriptRead],
    dependencies=[any_authenticated],
    include_in_schema=False,
)
async def list_scripts_legacy(
    system_id: UUID, db: AsyncSession = Depends(get_db)
) -> list[TestScriptRead]:
    return await TestScriptService(db).list_for_system(system_id)


@router.post(
    "/systems/{system_id}/scripts",
    response_model=TestScriptRead,
    status_code=201,
    dependencies=[any_authenticated],
    include_in_schema=False,
)
async def create_script_legacy(
    system_id: UUID, body: TestScriptCreate, db: AsyncSession = Depends(get_db)
) -> TestScriptRead:
    return await TestScriptService(db).create(system_id, body)


@router.get(
    "/scripts/{script_id}",
    response_model=TestScriptRead,
    dependencies=[any_authenticated],
    include_in_schema=False,
)
async def get_script_legacy(script_id: UUID, db: AsyncSession = Depends(get_db)) -> TestScriptRead:
    return await TestScriptService(db).get(script_id)


@router.put(
    "/scripts/{script_id}",
    response_model=TestScriptRead,
    dependencies=[any_authenticated],
    include_in_schema=False,
)
async def update_script_legacy(
    script_id: UUID, body: TestScriptUpdate, db: AsyncSession = Depends(get_db)
) -> TestScriptRead:
    return await TestScriptService(db).update(script_id, body)


@router.delete(
    "/scripts/{script_id}",
    status_code=204,
    response_model=None,
    dependencies=[can_manage_content],
    include_in_schema=False,
)
async def delete_script_legacy(script_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    await TestScriptService(db).delete(script_id)


@router.get(
    "/scripts/{script_id}/export/{format}",
    dependencies=[any_authenticated],
    include_in_schema=False,
)
async def export_script_legacy(
    script_id: UUID, format: str, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    content, media_type, filename = await TestScriptService(db).export(script_id, format)
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _get_bpo_domain(current_user: CurrentUser) -> str | None:
    """Return business_domain restriction for BPO users; None for everyone else."""
    for role in current_user.roles:
        if role.role == UserRoleEnum.BPO.value and role.business_domain:
            return role.business_domain
    return None


def _check_permission(current_user: CurrentUser, permission: Permission) -> None:
    """Ad-hoc permission check outside the require_system_access dependency chain."""
    if current_user.is_global_admin:
        return
    allowed: set[Permission] = set()
    for role in current_user.roles:
        role_enum_val = role.role  # role is stored as string value
        for role_enum, perms in ROLE_PERMISSIONS.items():
            if role_enum.value == role_enum_val:
                allowed.update(perms)
    if permission not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{permission.value}' required",
        )


# ── Bulk operations ───────────────────────────────────────────────────────────


class BulkScriptDeleteBody(BaseModel):
    ids: list[UUID]


class BulkScriptStatusBody(BaseModel):
    ids: list[UUID]
    new_status: str


class BulkOpResult(BaseModel):
    updated: int
    errors: list[str]


@router.post(
    "/systems/{system_id}/test-scripts/bulk-delete",
    response_model=BulkOpResult,
    dependencies=[can_manage_content],
    summary="Soft-delete multiple test scripts",
)
async def bulk_delete_scripts(
    system_id: UUID,
    body: BulkScriptDeleteBody,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BulkOpResult:
    if not body.ids:
        raise HTTPException(status_code=422, detail="ids must not be empty")
    svc = TestScriptService(db)
    deleted = 0
    errors: list[str] = []
    for script_id in body.ids:
        try:
            await svc.soft_delete(script_id)
            deleted += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{script_id}: {exc}")
    await db.commit()
    return BulkOpResult(updated=deleted, errors=errors)


@router.post(
    "/systems/{system_id}/test-scripts/bulk-status",
    response_model=BulkOpResult,
    dependencies=[can_manage_content],
    summary="Change status of multiple test scripts",
)
async def bulk_update_script_status(
    system_id: UUID,
    body: BulkScriptStatusBody,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BulkOpResult:
    from app.models.test_script import TestScript

    if not body.ids:
        raise HTTPException(status_code=422, detail="ids must not be empty")
    updated = 0
    errors: list[str] = []
    for script_id in body.ids:
        try:
            script = await db.get(TestScript, script_id)
            if script is None or script.deleted_at is not None or script.system_id != system_id:
                errors.append(f"{script_id}: not found")
                continue
            script.status = body.new_status
            updated += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{script_id}: {exc}")
    await db.commit()
    return BulkOpResult(updated=updated, errors=errors)
