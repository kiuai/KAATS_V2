from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

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
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)


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


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
