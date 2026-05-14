"""
KAATS Observability Bootstrap
==============================

Configures the two observability pillars in one place so every module can
import ``get_logger`` without worrying about initialisation order.

Logging (structlog)
-------------------
- Development : human-readable ConsoleRenderer with colours
- Production  : JSON lines suitable for Log Analytics / Application Insights

Every log record automatically inherits the per-request context variables
(correlation_id, request_id, user_id, company_id) that the middleware binds
via structlog.contextvars.

Tracing (OpenTelemetry)
-----------------------
- FastAPI, SQLAlchemy, and httpx are auto-instrumented.
- When ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set the Azure Monitor
  exporter sends traces and metrics to Application Insights.
- When ``OTLP_ENDPOINT`` is set a generic OTLP gRPC exporter is used instead.
- In CI / dev (neither variable set) a no-op OTLP exporter is used so the
  code path still works without any external service.

Usage
-----
Call ``configure_logging()`` once at process start (before any loggers are
created) and ``configure_telemetry(app)`` once after the FastAPI app is built.
"""
from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import structlog
from structlog.contextvars import merge_contextvars

if TYPE_CHECKING:
    from fastapi import FastAPI


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def configure_logging(log_level: str = "INFO", *, json: bool = True) -> None:
    """
    Configure structlog once.  Safe to call multiple times (idempotent).

    Parameters
    ----------
    log_level:
        Standard Python log-level string ("DEBUG", "INFO", "WARNING", …).
    json:
        ``True``  → JSON lines (production / CI)
        ``False`` → coloured console output (local dev)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # ── stdlib root logger ────────────────────────────────────────────────────
    # Route stdlib (uvicorn, sqlalchemy, azure-sdk, …) through structlog so
    # they share the same format and processors.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    # Silence noisy libraries in production
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if log_level.upper() != "DEBUG" else logging.DEBUG
    )
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)

    # ── Shared processors (applied to every log record) ───────────────────────
    shared_processors: list = [
        merge_contextvars,                          # pull correlation_id etc.
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json:
        # ── JSON renderer (production / CI) ───────────────────────────────────
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
        structlog.configure(
            processors=shared_processors + [renderer],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=True,
        )
    else:
        # ── Console renderer (local dev) ──────────────────────────────────────
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
            cache_logger_on_first_use=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tracing (OpenTelemetry)
# ─────────────────────────────────────────────────────────────────────────────

def configure_telemetry(
    fastapi_app: "FastAPI",
    *,
    service_name: str = "kaats-api",
    applicationinsights_connection_string: str | None = None,
    otlp_endpoint: str | None = None,
) -> None:
    """
    Wire OpenTelemetry instrumentation for FastAPI, SQLAlchemy, and httpx.

    Called once after the FastAPI app is built.  No-ops gracefully when
    the required packages are not installed (so unit tests stay fast).
    """
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        # OpenTelemetry packages not installed — skip silently
        return

    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
    })
    provider = TracerProvider(resource=resource)

    # ── Choose exporter ───────────────────────────────────────────────────────
    if applicationinsights_connection_string:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
            exporter = AzureMonitorTraceExporter(
                connection_string=applicationinsights_connection_string,
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            pass  # azure-monitor-opentelemetry-exporter not installed
    elif otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            pass
    # else: no exporter configured — traces are still created (visible in tests)

    trace.set_tracer_provider(provider)

    # ── Instrument libraries ──────────────────────────────────────────────────
    FastAPIInstrumentor.instrument_app(fastapi_app, tracer_provider=provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)

    # SQLAlchemy: instrumented separately once the engine is created.
    # Call instrument_sqlalchemy(engine) from database.py after engine init.

    log = structlog.get_logger(__name__)
    log.info(
        "telemetry.configured",
        service_name=service_name,
        exporter=(
            "azure_monitor" if applicationinsights_connection_string
            else "otlp" if otlp_endpoint
            else "none"
        ),
    )


def instrument_sqlalchemy(engine) -> None:  # type: ignore[type-arg]
    """Instrument a SQLAlchemy async engine.  Call once after engine creation."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except ImportError:
        pass
