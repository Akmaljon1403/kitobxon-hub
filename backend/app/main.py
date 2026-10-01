"""Kitobxon Hub backend entry point.

Run locally with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.database import dispose_engine
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.redis import close_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info("Starting %s %s (%s)", settings.app_name, settings.app_version, settings.environment)
    try:
        yield
    finally:
        await close_redis()
        await dispose_engine()
        logger.info("Shutdown complete")


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
    return app


app = create_app()
