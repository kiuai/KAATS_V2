from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException, Request, status

log = structlog.get_logger(__name__)

# ── Role predicates (used by route handlers for in-handler checks) ────────────


ALL_ROLES = frozenset({
    "global_admin",
    "enterprise_admin",
    "company_admin",
    "system_manager",
    "validation_lead",
    "qa",
    "validation_tester",
    "bpo",
})


def assert_roles(request: Request, *required: str) -> None:
    """
    Raise 403 if the current user does not hold at least one of ``required`` roles.
    For route-level checks prefer ``require_roles`` from dependencies.py.
    """
    user_roles: list[str] = getattr(request.state, "roles", [])
    if not set(required).intersection(user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


def has_role(request: Request, *roles: str) -> bool:
    user_roles: list[str] = getattr(request.state, "roles", [])
    return bool(set(roles).intersection(user_roles))


def is_platform_admin(request: Request) -> bool:
    return has_role(request, "global_admin")


# ── Correlation ID helpers ────────────────────────────────────────────────────


def get_correlation_id(request: Request) -> str:
    """Return the correlation ID for this request (set by TenantMiddleware)."""
    return getattr(request.state, "correlation_id", str(uuid4()))


# ── Audit logger ─────────────────────────────────────────────────────────────

# Actions that must be audit-logged (regardless of outcome).
AUDITED_ACTIONS: frozenset[str] = frozenset({
    "SCRIPT_APPROVE",
    "SCRIPT_DELETE",
    "USER_ASSIGN_ROLE",
    "AGENT_EXECUTE",
    "SCHEDULE_CREATE",
    "ADMIN_GLOBAL",
    "ADMIN_ENTERPRISE",
    "ADMIN_COMPANY",
})


class AuditLogger:
    """
    Writes structured audit events to Cosmos DB.
    All writes are best-effort and fire-and-forget — a Cosmos failure does not
    surface to the caller.

    Usage::

        audit = AuditLogger()
        await audit.log(
            request=request,
            action="SCRIPT_APPROVE",
            resource_id=script_id,
            outcome="success",
        )
    """

    _CONTAINER = "audit-log"

    async def log(
        self,
        request: Request,
        action: str,
        resource_id: UUID | str | None = None,
        outcome: str = "success",
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Fire-and-forget audit event. Failures are logged but not raised."""
        asyncio.ensure_future(
            self._write(request, action, resource_id, outcome, extra or {})
        )

    async def _write(
        self,
        request: Request,
        action: str,
        resource_id: UUID | str | None,
        outcome: str,
        extra: dict[str, Any],
    ) -> None:
        from app.cosmos import get_cosmos_database

        user_id: UUID | None = getattr(request.state, "user_id", None)
        company_id: UUID | None = getattr(request.state, "company_id", None)
        system_id: UUID | None = getattr(request.state, "system_id", None)
        correlation_id: str = get_correlation_id(request)

        doc: dict[str, Any] = {
            "id": str(uuid4()),
            "type": "audit_event",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id,
            "user_id": str(user_id) if user_id else None,
            "company_id": str(company_id) if company_id else None,
            "system_id": str(system_id) if system_id else None,
            "action": action,
            "resource_id": str(resource_id) if resource_id else None,
            "outcome": outcome,
            "path": request.url.path,
            "method": request.method,
            **extra,
        }

        try:
            db = get_cosmos_database()
            container = db.get_container_client(self._CONTAINER)
            await container.upsert_item(doc)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "audit.write_failed",
                action=action,
                resource_id=str(resource_id),
                error=str(exc),
            )


# Module-level singleton — import and call from route handlers.
audit_logger = AuditLogger()
