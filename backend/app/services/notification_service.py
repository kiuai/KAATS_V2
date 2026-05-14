"""Notification service — create and query in-app notifications."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

log = structlog.get_logger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        type: str = "info",
        body: str | None = None,
        action_url: str | None = None,
        company_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> Notification:
        """Create and persist a notification. Never raises."""
        try:
            n = Notification(
                user_id=user_id,
                company_id=company_id,
                type=type,
                title=title,
                body=body,
                action_url=action_url,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            self._db.add(n)
            await self._db.flush()
            return n
        except Exception:  # noqa: BLE001
            log.exception("notification.create.failed", user_id=str(user_id))
            raise

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        unread_only: bool = False,
        limit: int = 50,
        skip: int = 0,
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)  # noqa: E712
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def unread_count(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import func
        result = await self._db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        return int(result.scalar() or 0)

    async def mark_read(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Mark a single notification as read. Returns True if found."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await self._db.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(is_read=True, read_at=now)
        )
        return (result.rowcount or 0) > 0

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        """Mark all unread notifications as read. Returns count updated."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await self._db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=now)
        )
        return result.rowcount or 0
