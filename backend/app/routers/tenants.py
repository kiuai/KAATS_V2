"""Tenants router — Enterprise CRUD (GLOBAL_ADMIN) + Company CRUD (COMPANY_ADMIN+)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import can_manage_company, platform_admin_only
from app.dependencies import get_db
from app.schemas.tenant import (
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
    EnterpriseCreate,
    EnterpriseRead,
    EnterpriseUpdate,
)
from app.services.tenant_service import TenantService

router = APIRouter(tags=["tenants"])


# ── Enterprises (GLOBAL_ADMIN only) ──────────────────────────────────────────

@router.get("/admin/enterprises", response_model=list[EnterpriseRead], dependencies=[platform_admin_only])
async def list_enterprises(db: AsyncSession = Depends(get_db)) -> list[EnterpriseRead]:
    return await TenantService(db).list_enterprises()


@router.post("/admin/enterprises", response_model=EnterpriseRead, status_code=201, dependencies=[platform_admin_only])
async def create_enterprise(
    body: EnterpriseCreate,
    db: AsyncSession = Depends(get_db),
) -> EnterpriseRead:
    return await TenantService(db).create_enterprise(body)


@router.get("/admin/enterprises/{enterprise_id}", response_model=EnterpriseRead, dependencies=[platform_admin_only])
async def get_enterprise(
    enterprise_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EnterpriseRead:
    return await TenantService(db).get_enterprise(enterprise_id)


@router.patch("/admin/enterprises/{enterprise_id}", response_model=EnterpriseRead, dependencies=[platform_admin_only])
async def update_enterprise(
    enterprise_id: UUID,
    body: EnterpriseUpdate,
    db: AsyncSession = Depends(get_db),
) -> EnterpriseRead:
    return await TenantService(db).update_enterprise(enterprise_id, body)


# ── Companies ─────────────────────────────────────────────────────────────────

@router.get("/companies", response_model=list[CompanyRead], dependencies=[can_manage_company])
async def list_companies(
    enterprise_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[CompanyRead]:
    return await TenantService(db).list_companies(enterprise_id=enterprise_id)


@router.post("/companies", response_model=CompanyRead, status_code=201, dependencies=[can_manage_company])
async def create_company(
    body: CompanyCreate,
    db: AsyncSession = Depends(get_db),
) -> CompanyRead:
    return await TenantService(db).create_company(body)


@router.get("/companies/{company_id}", response_model=CompanyRead, dependencies=[can_manage_company])
async def get_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CompanyRead:
    return await TenantService(db).get_company(company_id)


@router.patch("/companies/{company_id}", response_model=CompanyRead, dependencies=[can_manage_company])
async def update_company(
    company_id: UUID,
    body: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
) -> CompanyRead:
    return await TenantService(db).update_company(company_id, body)


# Keep old /tenants prefix for backwards compat
@router.get("/tenants/enterprises", response_model=list[EnterpriseRead], dependencies=[platform_admin_only], include_in_schema=False)
async def list_enterprises_legacy(db: AsyncSession = Depends(get_db)) -> list[EnterpriseRead]:
    return await TenantService(db).list_enterprises()


@router.get("/tenants/companies", response_model=list[CompanyRead], dependencies=[can_manage_company], include_in_schema=False)
async def list_companies_legacy(db: AsyncSession = Depends(get_db)) -> list[CompanyRead]:
    return await TenantService(db).list_companies()


@router.post("/tenants/companies", response_model=CompanyRead, status_code=201, dependencies=[can_manage_company], include_in_schema=False)
async def create_company_legacy(body: CompanyCreate, db: AsyncSession = Depends(get_db)) -> CompanyRead:
    return await TenantService(db).create_company(body)


@router.get("/tenants/companies/{company_id}", response_model=CompanyRead, dependencies=[can_manage_company], include_in_schema=False)
async def get_company_legacy(company_id: UUID, db: AsyncSession = Depends(get_db)) -> CompanyRead:
    return await TenantService(db).get_company(company_id)


@router.put("/tenants/companies/{company_id}", response_model=CompanyRead, dependencies=[can_manage_company], include_in_schema=False)
async def update_company_legacy(company_id: UUID, body: CompanyUpdate, db: AsyncSession = Depends(get_db)) -> CompanyRead:
    return await TenantService(db).update_company(company_id, body)
