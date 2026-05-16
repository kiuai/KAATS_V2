"""Global search router.

GET /search?q=<term>   — cross-entity search, company-scoped
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import any_authenticated
from app.dependencies import get_current_company_id, get_db
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


class SearchResult(BaseModel):
    type: str
    id: str
    label: str
    description: str | None
    url: str


@router.get("", response_model=list[SearchResult], dependencies=[any_authenticated])
async def global_search(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, le=50),
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SearchResult]:
    company_id = get_current_company_id(request)
    results = await SearchService(db).search(
        q=q,
        company_id=company_id,
        limit=limit,
    )
    return [SearchResult(**r) for r in results]
