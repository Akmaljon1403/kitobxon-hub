"""Shared pytest fixtures.

Tests run against a real PostgreSQL database (constraints, locking and triggers are
part of what is being tested). Point ``TEST_DATABASE_URL`` at an empty, disposable
database; the default matches the CI service container. The suite drops and recreates
the ``public`` schema of that database.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/kitobxon_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-0123456789"
os.environ["BOT_TOKEN"] = "123456789:TEST-bot-token-AAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
os.environ["BOT_USERNAME"] = "kitobxon_test_bot"
os.environ["SUPER_ADMIN_TELEGRAM_IDS"] = "900000001"
os.environ.pop("REDIS_URL", None)
os.environ["WORKER_ENABLED"] = "false"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_LOCAL_PATH"] = tempfile.mkdtemp(prefix="kitobxon-test-storage-")
os.environ.pop("AI_API_KEY", None)

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import dispose_engine, get_engine, get_session_factory
from app.models import Base
from app.security.rate_limit import reset_in_memory_limits
from app.services.bootstrap import sync_reference_data

get_settings.cache_clear()

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["configure_logging"] = False
    config.attributes["database_url"] = os.environ["TEST_DATABASE_URL"]
    return config


@pytest.fixture(scope="session")
async def migrated_database() -> AsyncIterator[None]:
    """Fresh schema built by the real migrations (also exercising downgrade once)."""
    async with get_engine().begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
    config = alembic_config()
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.downgrade, config, "base")
    await asyncio.to_thread(command.upgrade, config, "head")
    yield


@pytest.fixture
async def db(migrated_database: None) -> AsyncIterator[AsyncSession]:
    """A clean database (all tables emptied, reference data re-seeded) for each test."""
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with get_session_factory()() as session:
        await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await session.commit()
        await sync_reference_data(session)
        yield session
        await session.rollback()


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.main import create_app

    return create_app(get_settings())


@pytest.fixture
async def client(app: FastAPI, db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    reset_in_memory_limits()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engine_at_end() -> AsyncIterator[None]:
    yield
    await dispose_engine()


@pytest.fixture(autouse=True)
def _no_required_subscription(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """The channel subscription check would ask Telegram; tests marked «subscription» keep it."""
    from app.services import subscription

    subscription.forget()
    if request.node.get_closest_marker("subscription"):
        return

    async def nothing_required(session: AsyncSession) -> list[tuple[str, str]]:
        return []

    monkeypatch.setattr(subscription, "configured", nothing_required)
