"""Webhooks router — manage company webhook endpoints.

GET    /webhooks                           — list endpoints
POST   /webhooks                           — create endpoint
GET    /webhooks/{id}                      — get endpoint
PATCH  /webhooks/{id}                      — update endpoint
DELETE /webhooks/{id}                      — delete endpoint
GET    /webhooks/{id}/deliveries           — delivery log
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import can_manage_company
from app.dependencies import get_current_company_id, get_db
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class WebhookEndpointCreate(BaseModel):
    url: str
    event_types: list[str] | None = None
    secret: str | None = None
    description: str | None = None


class WebhookEndpointUpdate(BaseModel):
    url: str | None = None
    event_types: list[str] | None = None
    secret: str | None = None
    description: str | None = None
    is_active: bool | None = None


class WebhookEndpointRead(BaseModel):
    id: UUID
    company_id: UUID
    url: str
    event_types: list[str] | None
    is_active: bool
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, ep) -> WebhookEndpointRead:  # type: ignore[override]
        return cls(
            id=ep.id,
            company_id=ep.company_id,
            url=ep.url,
            event_types=[e.strip() for e in ep.event_types.split(",")] if ep.event_types else None,
            is_active=ep.is_active,
            description=ep.description,
            created_at=ep.created_at,
        )


class WebhookDeliveryRead(BaseModel):
    id: UUID
    endpoint_id: UUID
    event_type: str
    response_status: int | None
    status: str
    attempt: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[WebhookEndpointRead], dependencies=[can_manage_company])
async def list_endpoints(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[WebhookEndpointRead]:
    company_id = get_current_company_id(request)
    eps = await WebhookService(db).list_endpoints(company_id)
    return [WebhookEndpointRead.from_orm_obj(ep) for ep in eps]


@router.post(
    "", response_model=WebhookEndpointRead, status_code=201, dependencies=[can_manage_company]
)
async def create_endpoint(
    body: WebhookEndpointCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WebhookEndpointRead:
    company_id = get_current_company_id(request)
    ep = await WebhookService(db).create_endpoint(
        company_id=company_id,
        url=body.url,
        event_types=body.event_types,
        secret=body.secret,
        description=body.description,
        created_by_id=current_user.user.id,
    )
    await db.commit()
    await db.refresh(ep)
    return WebhookEndpointRead.from_orm_obj(ep)


@router.get("/{endpoint_id}", response_model=WebhookEndpointRead, dependencies=[can_manage_company])
async def get_endpoint(
    endpoint_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> WebhookEndpointRead:
    company_id = get_current_company_id(request)
    ep = await WebhookService(db).get_endpoint(endpoint_id, company_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    return WebhookEndpointRead.from_orm_obj(ep)


@router.patch(
    "/{endpoint_id}", response_model=WebhookEndpointRead, dependencies=[can_manage_company]
)
async def update_endpoint(
    endpoint_id: UUID,
    body: WebhookEndpointUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> WebhookEndpointRead:
    company_id = get_current_company_id(request)
    ep = await WebhookService(db).update_endpoint(
        endpoint_id,
        company_id,
        url=body.url,
        event_types=body.event_types,
        secret=body.secret,
        description=body.description,
        is_active=body.is_active,
    )
    if ep is None:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    await db.commit()
    await db.refresh(ep)
    return WebhookEndpointRead.from_orm_obj(ep)


@router.delete(
    "/{endpoint_id}", status_code=204, response_model=None, dependencies=[can_manage_company]
)
async def delete_endpoint(
    endpoint_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> None:
    company_id = get_current_company_id(request)
    found = await WebhookService(db).delete_endpoint(endpoint_id, company_id)
    if not found:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    await db.commit()


@router.get(
    "/{endpoint_id}/deliveries",
    response_model=list[WebhookDeliveryRead],
    dependencies=[can_manage_company],
)
async def list_deliveries(
    endpoint_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(get_current_user),
) -> list[WebhookDeliveryRead]:
    company_id = get_current_company_id(request)
    # Verify ownership
    ep = await WebhookService(db).get_endpoint(endpoint_id, company_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    deliveries = await WebhookService(db).list_deliveries(endpoint_id, company_id)
    return [WebhookDeliveryRead.model_validate(d) for d in deliveries]
