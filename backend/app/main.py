from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.browser_pool import close_browser_pool, init_browser_pool
from app.blob import close_blob, init_blob
from app.config import get_settings
from app.cosmos import close_cosmos, init_cosmos
from app.database import close_db, init_db
from app.middleware.tenant import TenantMiddleware
from app.observability import configure_logging, configure_telemetry
from app.routers import (
    agents,
    auth,
    evidence,
    health,
    onboarding,
    reports,
    requirements,
    scheduler,
    systems,
    tenants,
    test_cycles,
    test_scripts,
    usage,
    users,
)

# ── Configure logging at import time so every subsequent get_logger() call
#    picks up the correct processors before the app is built.
_settings = get_settings()
configure_logging(
    log_level=_settings.log_level,
    json=_settings.is_production,
)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info("kaats.startup", environment=settings.environment)

    await init_db()
    try:
        await init_cosmos()
    except Exception as exc:  # noqa: BLE001
        log.warning("cosmos.startup_skipped", error=str(exc))
    await init_blob()
    try:
        await init_browser_pool(size=settings.browser_pool_size)
    except Exception as exc:  # noqa: BLE001
        log.warning("browser_pool.startup_skipped", error=str(exc))

    # ── Wire OpenTelemetry after all services are initialised ─────────────────
    configure_telemetry(
        app,
        service_name=settings.otel_service_name,
        applicationinsights_connection_string=settings.applicationinsights_connection_string,
        otlp_endpoint=settings.otlp_endpoint,
    )

    log.info("kaats.ready")
    yield

    log.info("kaats.shutdown")
    await close_browser_pool()
    await close_db()
    await close_cosmos()
    await close_blob()
    log.info("kaats.stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="KAATS API",
        description="KIU AI Agentic Test System",
        version="1.0.0",
        docs_url="/docs" if settings.openapi_enabled else None,
        redoc_url="/redoc" if settings.openapi_enabled else None,
        openapi_url="/openapi.json" if settings.openapi_enabled else None,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Tenant middleware (extracts JWT claims, sets RLS context, binds
    #    correlation_id / user_id / company_id to structlog context) ──────────
    app.add_middleware(TenantMiddleware)

    # ── Request ID + latency logging ──────────────────────────────────────────
    @app.middleware("http")
    async def request_logging(request: Request, call_next: any) -> Response:  # type: ignore[valid-type]
        request_id = str(uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        # Enrich with per-request context set by TenantMiddleware
        correlation_id = getattr(request.state, "correlation_id", None)
        user_id = str(getattr(request.state, "user_id", "") or "")
        company_id = str(getattr(request.state, "company_id", "") or "")

        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            correlation_id=correlation_id,
            user_id=user_id or None,
            company_id=company_id or None,
        )
        return response

    # ── Exception handlers ────────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        correlation_id = getattr(request.state, "correlation_id", None)
        log.exception(
            "http.unhandled_error",
            request_id=request_id,
            correlation_id=correlation_id,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "details": None,
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                }
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    PREFIX = "/api/v1"
    app.include_router(health.router)   # no prefix — /health/live, /health/ready
    app.include_router(auth.router, prefix=PREFIX)
    app.include_router(tenants.router, prefix=PREFIX)
    app.include_router(users.router, prefix=PREFIX)
    app.include_router(systems.router, prefix=PREFIX)
    app.include_router(requirements.router, prefix=PREFIX)
    app.include_router(test_scripts.router, prefix=PREFIX)
    app.include_router(test_cycles.router, prefix=PREFIX)
    app.include_router(agents.router, prefix=PREFIX)
    app.include_router(scheduler.router, prefix=PREFIX)
    app.include_router(evidence.router, prefix=PREFIX)
    app.include_router(reports.router, prefix=PREFIX)
    app.include_router(onboarding.router, prefix=PREFIX)
    app.include_router(usage.router, prefix=PREFIX)

    return app


app = create_app()
