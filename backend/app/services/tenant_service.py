"""Tenant service — Enterprise and Company CRUD with admin guards."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Company, Enterprise
from app.schemas.tenant import (
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
    EnterpriseCreate,
    EnterpriseRead,
    EnterpriseUpdate,
)

log = structlog.get_logger(__name__)


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Enterprises ───────────────────────────────────────────────────────────

    async def list_enterprises(self) -> list[EnterpriseRead]:
        result = await self._db.execute(
            select(Enterprise).where(Enterprise.is_active.is_(True)).order_by(Enterprise.name)
        )
        return [EnterpriseRead.model_validate(row) for row in result.scalars().all()]

    async def get_enterprise(self, enterprise_id: UUID) -> EnterpriseRead:
        enterprise = await self._db.get(Enterprise, enterprise_id)
        if not enterprise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enterprise not found",
            )
        return EnterpriseRead.model_validate(enterprise)

    async def create_enterprise(self, body: EnterpriseCreate) -> EnterpriseRead:
        existing = await self._db.scalar(select(Enterprise).where(Enterprise.slug == body.slug))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Enterprise with slug '{body.slug}' already exists",
            )
        enterprise = Enterprise(**body.model_dump())
        self._db.add(enterprise)
        await self._db.flush()
        log.info("enterprise.created", enterprise_id=str(enterprise.id), slug=body.slug)
        return EnterpriseRead.model_validate(enterprise)

    async def update_enterprise(
        self,
        enterprise_id: UUID,
        body: EnterpriseUpdate,
    ) -> EnterpriseRead:
        enterprise = await self._db.get(Enterprise, enterprise_id)
        if not enterprise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enterprise not found",
            )
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(enterprise, field, value)
        await self._db.flush()
        log.info("enterprise.updated", enterprise_id=str(enterprise_id))
        return EnterpriseRead.model_validate(enterprise)

    # ── Companies ─────────────────────────────────────────────────────────────

    async def list_companies(self, enterprise_id: UUID | None = None) -> list[CompanyRead]:
        q = select(Company).where(Company.is_active.is_(True))
        if enterprise_id:
            q = q.where(Company.enterprise_id == enterprise_id)
        q = q.order_by(Company.name)
        result = await self._db.execute(q)
        return [CompanyRead.model_validate(row) for row in result.scalars().all()]

    async def get_company(self, company_id: UUID) -> CompanyRead:
        company = await self._db.get(Company, company_id)
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )
        return CompanyRead.model_validate(company)

    async def create_company(self, body: CompanyCreate) -> CompanyRead:
        existing = await self._db.scalar(select(Company).where(Company.slug == body.slug))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company with slug '{body.slug}' already exists",
            )
        data = body.model_dump()
        if hasattr(data.get("default_export_format"), "value"):
            data["default_export_format"] = data["default_export_format"].value
        company = Company(**data)
        self._db.add(company)
        await self._db.flush()
        log.info("company.created", company_id=str(company.id), slug=body.slug)
        return CompanyRead.model_validate(company)

    async def update_company(self, company_id: UUID, body: CompanyUpdate) -> CompanyRead:
        company = await self._db.get(Company, company_id)
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )
        data = body.model_dump(exclude_none=True)
        if "default_export_format" in data and hasattr(data["default_export_format"], "value"):
            data["default_export_format"] = data["default_export_format"].value
        for field, value in data.items():
            setattr(company, field, value)
        await self._db.flush()
        log.info("company.updated", company_id=str(company_id))
        return CompanyRead.model_validate(company)
