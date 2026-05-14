"""Audit logging service.

Provides a single ``log()`` method that appends an ``AuditLog`` row to the
current DB session.  The caller is responsible for committing (the row is
committed together with the rest of the request transaction).

Usage inside a FastAPI route::

    await AuditService(db).log(
        event_type="user.role_assigned",
        actor_user_id=current_user.user.id,
        actor_email=current_user.user.email,
        company_id=company_id,
        resource_type="user",
        resource_id=str(target_user_id),
        changes={"after": {"role": role_name}},
        request=request,   # optional — extracts IP + correlation_id
    )

All exceptions are swallowed so audit failures never break business logic.
"""
from __future__ import annotations

import structlog
from uuid import UUID
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

log = structlog.get_logger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def log(
        self,
        *,
        event_type: str,
        actor_user_id: UUID | None = None,
        actor_email: str | None = None,
        company_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        changes: dict[str, Any] | None = None,
        request: Request | None = None,
        ip_address: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Append an audit log entry.  Never raises."""
        try:
            ip = ip_address
            corr = correlation_id
            if request is not None:
                if ip is None and request.client:
                    ip = request.client.host
                if corr is None:
                    corr = getattr(request.state, "correlation_id", None)

            entry = AuditLog(
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                company_id=company_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                changes=changes,
                ip_address=ip,
                correlation_id=str(corr) if corr else None,
            )
            self._db.add(entry)
            await self._db.flush()
        except Exception as exc:  # noqa: BLE001
            log.warning("audit.log_failed", event_type=event_type, error=str(exc))

    async def list_logs(
        self,
        *,
        company_id: UUID | None = None,
        event_type: str | None = None,
        actor_user_id: UUID | None = None,
        from_dt: Any | None = None,
        to_dt: Any | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AuditLog]:
        from sqlalchemy import and_

        stmt = select(AuditLog)
        filters = []

        if company_id is not None:
            filters.append(AuditLog.company_id == company_id)
        if event_type is not None:
            filters.append(AuditLog.event_type == event_type)
        if actor_user_id is not None:
            filters.append(AuditLog.actor_user_id == actor_user_id)
        if from_dt is not None:
            filters.append(AuditLog.created_at >= from_dt)
        if to_dt is not None:
            filters.append(AuditLog.created_at <= to_dt)

        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
