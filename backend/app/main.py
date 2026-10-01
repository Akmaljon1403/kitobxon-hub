"""Kitobxon Hub backend entry point.

Run locally with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.bot.setup import close_bot_runtime, configure_telegram, get_bot_runtime
from app.bot.webhook import router as telegram_router
from app.core.config import Settings, get_settings
from app.core.database import dispose_engine, get_session_factory
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.redis import close_redis
from app.services.bootstrap import sync_reference_data

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info("Starting %s %s (%s)", settings.app_name, settings.app_version, settings.environment)
    await _bootstrap_reference_data()
    await _configure_bot(settings)
    try:
        yield
    finally:
        await close_bot_runtime()
        await close_redis()
        await dispose_engine()
        logger.info("Shutdown complete")


async def _bootstrap_reference_data() -> None:
    """Make sure permissions, roles and default settings exist. Never prevents start-up:
    if the database is unreachable the problem is reported by /health/db instead."""
    try:
        async with get_session_factory()() as session:
            await sync_reference_data(session)
    except Exception:
        logger.exception("Reference data bootstrap failed (are migrations applied? run: alembic upgrade head)")


async def _configure_bot(settings: Settings) -> None:
    """Register the webhook, commands and menu button with Telegram (webhook mode only)."""
    if settings.bot_mode != "webhook":
        return
    runtime = get_bot_runtime()
    if runtime is None:
        logger.info("Telegram bot disabled (BOT_TOKEN is not set)")
        return
    try:
        await configure_telegram(runtime, with_webhook=True)
    except Exception:
        logger.exception("Could not configure the Telegram bot; the API keeps running")


def _mount_frontends(app: FastAPI, settings: Settings) -> None:
    """Serve the built Mini App (/app/) and Admin Panel (/admin/) when they are present."""
    static_root = Path(settings.static_dir)
    for prefix, folder in (("/app", "miniapp"), ("/admin", "admin")):
        directory = static_root / folder
        if (directory / "index.html").is_file():
            app.mount(prefix, StaticFiles(directory=directory, html=True), name=folder)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description="Kitobxon Hub — kitobxonlar klubi uchun boshqaruv platformasi API.",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.api_docs_enabled else None,
        redoc_url="/api/redoc" if settings.api_docs_enabled else None,
        openapi_url="/api/openapi.json" if settings.api_docs_enabled else None,
    )
    app.state.settings = settings

    register_error_handlers(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
            expose_headers=["X-Request-ID", "Retry-After"],
            max_age=600,
        )
    # Added last so it is the outermost middleware and sees every request.
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(api_router)
    app.include_router(telegram_router)
    _mount_frontends(app, settings)
    return app


app = create_app()
