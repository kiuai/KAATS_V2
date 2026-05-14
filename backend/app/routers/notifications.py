"""In-app notifications router.

GET  /notifications              — list (with optional ?unread_only=true)
GET  /notifications/count        — unread count
PATCH /notifications/{id}/read   — mark single as read
PATCH /notifications/read-all    — mark all as read
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import any_authenticated
from app.dependencies import get_db
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ── Response schema ───────────────────────────────────────────────────────────


class NotificationRead(BaseModel):
    id: UUID
    type: str
    title: str
    body: str | None
    action_url: str | None
    resource_type: str | None
    resource_id: str | None
    is_read: bool
    created_at: str  # ISO string — simpler for frontend

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[NotificationRead], dependencies=[any_authenticated])
async def list_notifications(
    unread_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationRead]:
    rows = await NotificationService(db).list_for_user(
        current_user.user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    return [
        NotificationRead(
            id=n.id,
            type=n.type,
            title=n.title,
            body=n.body,
            action_url=n.action_url,
            resource_type=n.resource_type,
            resource_id=n.resource_id,
            is_read=n.is_read,
            created_at=n.created_at.isoformat(),
        )
        for n in rows
    ]


@router.get("/count", response_model=UnreadCountResponse, dependencies=[any_authenticated])
async def get_unread_count(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    count = await NotificationService(db).unread_count(current_user.user.id)
    return UnreadCountResponse(count=count)


@router.patch(
    "/read-all",
    response_model=UnreadCountResponse,
    dependencies=[any_authenticated],
    summary="Mark all notifications as read",
)
async def mark_all_read(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    updated = await NotificationService(db).mark_all_read(current_user.user.id)
    await db.commit()
    return UnreadCountResponse(count=updated)


@router.patch(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[any_authenticated],
)
async def mark_read(
    notification_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    found = await NotificationService(db).mark_read(notification_id, current_user.user.id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.commit()
