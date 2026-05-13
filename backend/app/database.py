from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import structlog
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

log = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    engine = create_async_engine(
        settings.sqlalchemy_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=not settings.is_production,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_conn: Any, _: Any) -> None:
        # Disable autocommit so we control transactions explicitly
        dbapi_conn.autocommit = False

    return engine


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autobegin=True,
        )
    return _session_factory


async def set_tenant_context(conn: AsyncConnection, company_id: str) -> None:
    """Set SESSION_CONTEXT for RLS filtering. Must be called on every connection."""
    await conn.execute(
        text(
            "EXEC sp_set_session_context "
            "@key = N'tenant_id', "
            ":value, "
            "@read_only = 1"
        ),
        {"value": company_id},
    )


async def get_db(company_id: str | None = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency-style session generator. Callers normally use the FastAPI
    dependency in ``dependencies.py`` which injects the company_id from the request.
    """
    factory = get_session_factory()
    async with factory() as session:
        if company_id:
            conn = await session.connection()
            await set_tenant_context(conn, company_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Verify connectivity at startup. Migrations are handled by Alembic."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("database.connected")


async def close_db() -> None:
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    log.info("database.closed")
