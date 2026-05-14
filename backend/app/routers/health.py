"""
Health check endpoints.

GET /health/live   — Liveness: always 200 if the process is running.
                     Kubernetes / Container Apps restarts the pod if this fails.

GET /health/ready  — Readiness: 200 when all critical dependencies are up,
                     503 when any critical dependency is unavailable.
                     Container Apps removes the replica from the load balancer
                     until ready again.

Both endpoints are public (no authentication required).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

log = structlog.get_logger(__name__)

router = APIRouter(tags=["ops"])


# ─────────────────────────────────────────────────────────────────────────────
# Liveness
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health/live", include_in_schema=False)
async def liveness() -> dict[str, str]:
    """Always 200 — proves the process is alive."""
    return {"status": "alive"}


# ─────────────────────────────────────────────────────────────────────────────
# Readiness
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health/ready", include_in_schema=False)
async def readiness() -> JSONResponse:
    """
    Checks all critical dependencies in parallel (2 s timeout each).
    Returns 200 if all pass, 503 if any critical check fails.
    """
    t0 = time.perf_counter()

    results = await asyncio.gather(
        _check_database(),
        _check_cosmos(),
        _check_service_bus(),
        _check_blob(),
        return_exceptions=True,
    )

    checks: dict[str, Any] = {}
    all_ok = True

    labels = ["database", "cosmos", "service_bus", "blob"]
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            checks[label] = {"status": "degraded", "error": str(result)}
            all_ok = False
        else:
            checks[label] = result
            if result.get("status") != "ok":
                all_ok = False

    duration_ms = round((time.perf_counter() - t0) * 1000)
    overall = "ok" if all_ok else "degraded"

    log.info(
        "health.readiness",
        status=overall,
        duration_ms=duration_ms,
        **{f"check_{k}": v.get("status", "error") for k, v in checks.items()},
    )

    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": overall,
            "checks": checks,
            "duration_ms": duration_ms,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Individual dependency probes
# ─────────────────────────────────────────────────────────────────────────────

async def _check_database() -> dict[str, Any]:
    try:
        from sqlalchemy import text
        from app.database import get_session_factory
        async with asyncio.timeout(2.0):
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except TimeoutError:
        return {"status": "degraded", "error": "timeout"}
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)[:120]}


async def _check_cosmos() -> dict[str, Any]:
    try:
        from app.cosmos import get_cosmos_client
        async with asyncio.timeout(2.0):
            client = get_cosmos_client()
            # list_databases is a lightweight metadata call
            async for _ in client.list_databases():
                break
        return {"status": "ok"}
    except TimeoutError:
        return {"status": "degraded", "error": "timeout"}
    except Exception as exc:
        # Cosmos is non-critical (audit logs) — degrade gracefully
        return {"status": "degraded", "error": str(exc)[:120]}


async def _check_service_bus() -> dict[str, Any]:
    try:
        from azure.servicebus.management.aio import ServiceBusAdministrationClient
        from app.config import get_settings
        settings = get_settings()
        async with asyncio.timeout(2.0):
            async with ServiceBusAdministrationClient.from_connection_string(
                settings.azure_service_bus_connection_string,
            ) as admin_client:
                await admin_client.get_namespace_properties()
        return {"status": "ok"}
    except TimeoutError:
        return {"status": "degraded", "error": "timeout"}
    except Exception as exc:
        # Service Bus is non-critical for inbound API requests
        return {"status": "degraded", "error": str(exc)[:120]}


async def _check_blob() -> dict[str, Any]:
    try:
        from azure.storage.blob.aio import BlobServiceClient
        from app.config import get_settings
        settings = get_settings()
        async with asyncio.timeout(2.0):
            async with BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string,
            ) as client:
                await client.get_service_properties()
        return {"status": "ok"}
    except TimeoutError:
        return {"status": "degraded", "error": "timeout"}
    except Exception as exc:
        return {"status": "degraded", "error": str(exc)[:120]}
