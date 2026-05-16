"""Audit log router.

GET /api/v1/audit/logs  — paginated audit log (audit:log_read permission)

Global admins see all logs (cross-company).
Enterprise / company admins see only their company's logs.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import CurrentUser, get_current_user
from app.auth.permissions import can_read_audit
from app.dependencies import get_db
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


# ── Response schema ───────────────────────────────────────────────────────────


class AuditLogRead(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    actor_email: str | None
    company_id: UUID | None
    event_type: str
    resource_type: str | None
    resource_id: str | None
    changes: dict | None
    ip_address: str | None
    correlation_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get(
    "/logs",
    response_model=list[AuditLogRead],
    dependencies=[can_read_audit],
    summary="Paginated audit log",
)
async def list_audit_logs(
    request: Request,
    event_type: str | None = Query(default=None),
    actor_user_id: UUID | None = Query(default=None),
    from_dt: datetime | None = Query(default=None),
    to_dt: datetime | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[AuditLogRead]:
    # Global admins see all; everyone else is scoped to their company
    company_id: UUID | None = None
    if not current_user.is_global_admin:
        company_id = getattr(request.state, "company_id", None)

    rows = await AuditService(db).list_logs(
        company_id=company_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        from_dt=from_dt,
        to_dt=to_dt,
        skip=skip,
        limit=limit,
    )
    return [AuditLogRead.model_validate(r) for r in rows]
