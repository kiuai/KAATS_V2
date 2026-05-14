from __future__ import annotations

import asyncio
import struct
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import event, pool

from app.config import get_settings
from app.models.base import Base
import app.models.tenant  # noqa: F401
import app.models.user  # noqa: F401
import app.models.role  # noqa: F401
import app.models.system  # noqa: F401
import app.models.requirement  # noqa: F401
import app.models.test_script  # noqa: F401
import app.models.test_cycle  # noqa: F401
import app.models.test_result  # noqa: F401
import app.models.execution_evidence  # noqa: F401
import app.models.crawl_job  # noqa: F401
import app.models.scheduled_job  # noqa: F401
import app.models.agent_run  # noqa: F401
import app.models.plan  # noqa: F401
import app.models.invitation  # noqa: F401
import app.models.onboarding  # noqa: F401
import app.models.audit_log  # noqa: F401
import app.models.notification  # noqa: F401
import app.models.webhook  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()  # type: ignore[call-arg]
# NOTE: We intentionally do NOT call config.set_main_option("sqlalchemy.url", ...)
# because the odbc_connect URL form contains %-encoded characters that confuse
# SafeConfigParser's interpolation.  Instead the engine is built directly in
# run_async_migrations() below.


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def _maybe_add_token_injection(engine: Any, url: str, client_id: str) -> None:
    """Inject AAD access token into pyodbc when ActiveDirectoryMsi auth is used.

    Works around the ODBC Driver's own MSI implementation timing out in Container
    Apps VNet environments by pre-fetching the token via azure-identity instead.
    """
    if "authentication=activedirectorymsi" not in url.lower():  # url is database_url (original)
        return
    try:
        from azure.identity import ManagedIdentityCredential

        _credential = ManagedIdentityCredential(client_id=client_id)
        _SQL_COPT_SS_ACCESS_TOKEN = 1256

        @event.listens_for(engine.sync_engine, "do_connect")
        def _inject_token(dialect: Any, conn_rec: Any, cargs: Any, cparams: Any) -> None:
            token = _credential.get_token("https://database.windows.net/.default")
            token_bytes = token.token.encode("utf-16-le")
            token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
            cparams["attrs_before"] = {_SQL_COPT_SS_ACCESS_TOKEN: token_struct}

    except ImportError:
        pass  # azure-identity not installed; fall back to ODBC MSI flow


async def run_async_migrations() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    # Build the engine directly so the URL never passes through SafeConfigParser
    # (which chokes on %-encoded characters in the odbc_connect form).
    connectable = create_async_engine(
        settings.sqlalchemy_url,
        poolclass=pool.NullPool,
    )
    _maybe_add_token_injection(connectable, settings.database_url, settings.azure_client_id)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
