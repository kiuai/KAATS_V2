from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Company, Enterprise
from app.schemas.tenant import CompanyCreate, CompanyRead, CompanyUpdate, EnterpriseRead


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_enterprises(self) -> list[EnterpriseRead]:
        result = await self._db.execute(select(Enterprise).where(Enterprise.is_active.is_(True)))
        return [EnterpriseRead.model_validate(row) for row in result.scalars().all()]

    async def list_companies(self) -> list[CompanyRead]:
        result = await self._db.execute(select(Company).where(Company.is_active.is_(True)))
        return [CompanyRead.model_validate(row) for row in result.scalars().all()]

    async def create_company(self, body: CompanyCreate) -> CompanyRead:
        company = Company(**body.model_dump())
        self._db.add(company)
        await self._db.flush()
        return CompanyRead.model_validate(company)

    async def get_company(self, company_id: UUID) -> CompanyRead:
        company = await self._db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
        return CompanyRead.model_validate(company)

    async def update_company(self, company_id: UUID, body: CompanyUpdate) -> CompanyRead:
        company = await self._db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(company, field, value)
        await self._db.flush()
        return CompanyRead.model_validate(company)
