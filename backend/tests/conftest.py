"""Shared pytest fixtures.

Tests run against a real PostgreSQL database (constraints, locking and triggers are
part of what is being tested). Point ``TEST_DATABASE_URL`` at an empty database;
the default matches the CI service container.
"""

from __future__ import annotations

import os

os.environ.setdefault("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/kitobxon_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-0123456789"
os.environ["BOT_TOKEN"] = "123456789:TEST-bot-token-AAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
os.environ["BOT_USERNAME"] = "kitobxon_test_bot"
os.environ.pop("REDIS_URL", None)

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import dispose_engine

get_settings.cache_clear()


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.main import create_app

    return create_app(get_settings())


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engine_at_end() -> AsyncIterator[None]:
    yield
    await dispose_engine()
