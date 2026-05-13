from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import can_manage_company, platform_admin_only
from app.dependencies import get_db
from app.schemas.tenant import CompanyCreate, CompanyRead, CompanyUpdate, EnterpriseRead
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/enterprises", response_model=list[EnterpriseRead], dependencies=[platform_admin_only])
async def list_enterprises(db: AsyncSession = Depends(get_db)) -> list[EnterpriseRead]:
    return await TenantService(db).list_enterprises()


@router.get("/companies", response_model=list[CompanyRead], dependencies=[can_manage_company])
async def list_companies(db: AsyncSession = Depends(get_db)) -> list[CompanyRead]:
    return await TenantService(db).list_companies()


@router.post("/companies", response_model=CompanyRead, status_code=201, dependencies=[can_manage_company])
async def create_company(
    body: CompanyCreate, db: AsyncSession = Depends(get_db)
) -> CompanyRead:
    return await TenantService(db).create_company(body)


@router.get("/companies/{company_id}", response_model=CompanyRead, dependencies=[can_manage_company])
async def get_company(company_id: UUID, db: AsyncSession = Depends(get_db)) -> CompanyRead:
    return await TenantService(db).get_company(company_id)


@router.put("/companies/{company_id}", response_model=CompanyRead, dependencies=[can_manage_company])
async def update_company(
    company_id: UUID, body: CompanyUpdate, db: AsyncSession = Depends(get_db)
) -> CompanyRead:
    return await TenantService(db).update_company(company_id, body)
