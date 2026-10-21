"""Alembic migration environment (async, asyncpg).

The database URL comes from application settings (DATABASE_URL), so migrations always
target the same database as the running application.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database() -> tuple[str, dict]:
    override = config.attributes.get("database_url")
    if override:
        from app.core.config import normalize_database_url

        return normalize_database_url(override)
    return get_settings().sqlalchemy_database


def run_migrations_offline() -> None:
    """Generate SQL without connecting (``alembic upgrade head --sql``)."""
    url, _ = _database()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# Arbitrary constant: serialises migrations when several containers start at the same time.
_MIGRATION_LOCK_ID = 7_243_001


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        # Never let a migration hang the whole deploy. During a rolling deploy the previous
        # instance is still serving, so a brief lock on a busy table (events, campaigns, …) can
        # delay an ALTER. Bound the waits: a blocked DDL aborts in a few seconds (lock_timeout)
        # and any single statement — including the advisory lock below — in a couple of minutes
        # (statement_timeout). start.sh then exits with a clear message and the platform retries,
        # instead of the server never binding its port and the deploy timing out silently.
        connection.execute(text("SET LOCAL lock_timeout = '15s'"))
        connection.execute(text("SET LOCAL statement_timeout = '120s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _MIGRATION_LOCK_ID})
        context.run_migrations()


async def run_async_migrations() -> None:
    url, connect_args = _database()
    # Same as the application engine: works through transaction-pooling proxies (Neon pooled URLs).
    engine = create_async_engine(url, poolclass=pool.NullPool, connect_args={**connect_args, "statement_cache_size": 0})
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
