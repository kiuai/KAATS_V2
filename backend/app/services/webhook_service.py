"""Webhook delivery service.

Responsible for:
- CRUD on WebhookEndpoint (per-company)
- Firing payloads to registered endpoints (fire-and-forget, best-effort)
- Recording WebhookDelivery rows
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookDelivery, WebhookEndpoint

log = structlog.get_logger(__name__)

_DELIVERY_TIMEOUT = 10.0  # seconds


class WebhookService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Endpoint CRUD ─────────────────────────────────────────────────────────

    async def list_endpoints(self, company_id: uuid.UUID) -> list[WebhookEndpoint]:
        result = await self._db.execute(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.company_id == company_id)
            .order_by(WebhookEndpoint.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_endpoint(
        self, endpoint_id: uuid.UUID, company_id: uuid.UUID
    ) -> WebhookEndpoint | None:
        result = await self._db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.id == endpoint_id,
                WebhookEndpoint.company_id == company_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_endpoint(
        self,
        *,
        company_id: uuid.UUID,
        url: str,
        event_types: list[str] | None = None,
        secret: str | None = None,
        description: str | None = None,
        created_by_id: uuid.UUID | None = None,
    ) -> WebhookEndpoint:
        ep = WebhookEndpoint(
            company_id=company_id,
            url=url,
            event_types=",".join(event_types) if event_types else None,
            secret=secret,
            description=description,
            created_by_id=created_by_id,
        )
        self._db.add(ep)
        await self._db.flush()
        return ep

    async def update_endpoint(
        self,
        endpoint_id: uuid.UUID,
        company_id: uuid.UUID,
        *,
        url: str | None = None,
        event_types: list[str] | None = None,
        secret: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> WebhookEndpoint | None:
        ep = await self.get_endpoint(endpoint_id, company_id)
        if ep is None:
            return None
        if url is not None:
            ep.url = url
        if event_types is not None:
            ep.event_types = ",".join(event_types) if event_types else None
        if secret is not None:
            ep.secret = secret
        if description is not None:
            ep.description = description
        if is_active is not None:
            ep.is_active = is_active
        await self._db.flush()
        return ep

    async def delete_endpoint(self, endpoint_id: uuid.UUID, company_id: uuid.UUID) -> bool:
        ep = await self.get_endpoint(endpoint_id, company_id)
        if ep is None:
            return False
        await self._db.delete(ep)
        await self._db.flush()
        return True

    # ── Delivery ──────────────────────────────────────────────────────────────

    async def dispatch(
        self,
        *,
        company_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Fire event to all matching active endpoints. Never raises."""
        try:
            result = await self._db.execute(
                select(WebhookEndpoint).where(
                    WebhookEndpoint.company_id == company_id,
                    WebhookEndpoint.is_active == True,  # noqa: E712
                )
            )
            endpoints = list(result.scalars().all())
        except Exception:  # noqa: BLE001
            log.exception("webhook.dispatch.query_failed", event_type=event_type)
            return

        for ep in endpoints:
            # Check event subscription filter
            if ep.event_types:
                subscribed = {e.strip() for e in ep.event_types.split(",")}
                if event_type not in subscribed:
                    continue
            await self._deliver(ep, event_type, payload)

    async def _deliver(
        self,
        endpoint: WebhookEndpoint,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        body_bytes = json.dumps(payload).encode()
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-KAATS-Event": event_type,
        }
        if endpoint.secret:
            sig = hmac.new(
                endpoint.secret.encode(),
                body_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-KAATS-Signature"] = f"sha256={sig}"

        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            company_id=endpoint.company_id,
            event_type=event_type,
            payload=payload,
            status="pending",
        )
        self._db.add(delivery)
        try:
            await self._db.flush()
        except Exception:  # noqa: BLE001
            pass

        try:
            async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT) as client:
                resp = await client.post(endpoint.url, content=body_bytes, headers=headers)
            delivery.response_status = resp.status_code
            delivery.response_body = resp.text[:2000]
            delivery.status = "success" if resp.is_success else "failed"
            delivery.delivered_at = datetime.now(UTC).replace(tzinfo=None)
            log.info(
                "webhook.delivered",
                endpoint_id=str(endpoint.id),
                event_type=event_type,
                status=resp.status_code,
            )
        except Exception as exc:  # noqa: BLE001
            delivery.status = "failed"
            delivery.error = str(exc)[:500]
            log.warning(
                "webhook.delivery.failed",
                endpoint_id=str(endpoint.id),
                event_type=event_type,
                error=str(exc),
            )
        try:
            await self._db.flush()
        except Exception:  # noqa: BLE001
            pass

    # ── Delivery history ──────────────────────────────────────────────────────

    async def list_deliveries(
        self,
        endpoint_id: uuid.UUID,
        company_id: uuid.UUID,
        limit: int = 50,
    ) -> list[WebhookDelivery]:
        result = await self._db.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.endpoint_id == endpoint_id,
                WebhookDelivery.company_id == company_id,
            )
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
