from __future__ import annotations

import struct
import uuid
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

import structlog
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import Select

from app.config import get_settings

_T = TypeVar("_T")

log = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# SQL_COPT_SS_ACCESS_TOKEN for injecting AAD tokens directly into pyodbc
_SQL_COPT_SS_ACCESS_TOKEN = 1256


def _make_token_struct(token: str) -> bytes:
    """Encode an AAD bearer token into the binary format pyodbc expects."""
    token_bytes = token.encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    engine = create_async_engine(
        settings.sqlalchemy_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=settings.db_pool_timeout,
        echo=not settings.is_production,
    )

    # When the URL uses ActiveDirectoryMsi, bypass the ODBC driver's own MSI
    # implementation (which times out in Container Apps VNet) by injecting a
    # pre-fetched token via SQL_COPT_SS_ACCESS_TOKEN. The token takes precedence
    # over the Authentication= keyword so both can coexist in the connection string.
    if "authentication=activedirectorymsi" in settings.database_url.lower():
        try:
            from azure.identity import ManagedIdentityCredential

            _msi_credential = ManagedIdentityCredential(client_id=settings.azure_client_id)

            @event.listens_for(engine.sync_engine, "do_connect")
            def _inject_token(dialect: Any, conn_rec: Any, cargs: Any, cparams: Any) -> None:
                token = _msi_credential.get_token("https://database.windows.net/.default")
                cparams["attrs_before"] = {_SQL_COPT_SS_ACCESS_TOKEN: _make_token_struct(token.token)}

        except ImportError:
            log.warning("azure_identity.not_installed", detail="token injection unavailable")

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


async def set_tenant_context(conn: AsyncConnection, company_id: Any) -> None:
    """Set SESSION_CONTEXT for RLS filtering. Must be called on every connection."""
    # SQL Server requires all sp_set_session_context params to use @name=value form.
    # The value must be a string (sql_variant); cast UUID if needed.
    value = str(company_id) if not isinstance(company_id, str) else company_id
    await conn.execute(
        text(
            "EXEC sp_set_session_context "
            "@key = N'tenant_id', "
            "@value = :value, "
            "@read_only = 1"
        ),
        {"value": value},
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


# Alias for FastAPI dependencies that prefer this name
get_async_session = get_db


def scoped_select(model: type[_T], company_id: uuid.UUID) -> Select:
    """
    Return a SELECT statement pre-filtered to a specific company.

    Usage::

        stmt = scoped_select(Requirement, company_id).where(Requirement.status == "active")
        result = await db.scalars(stmt)
    """
    return select(model).where(model.company_id == company_id)  # type: ignore[attr-defined]


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
