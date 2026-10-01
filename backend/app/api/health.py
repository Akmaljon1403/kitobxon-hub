"""Health endpoints used by hosting platforms and uptime monitors."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import get_engine
from app.core.errors import ServiceUnavailableError
from app.core.redis import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

_CHECK_TIMEOUT_SECONDS = 5


class HealthStatus(BaseModel):
    status: Literal["ok", "not_configured"]
    service: str
    version: str | None = None
    environment: str | None = None


@router.get("", response_model=HealthStatus, summary="Application liveness")
async def health() -> HealthStatus:
    settings = get_settings()
    return HealthStatus(status="ok", service="api", version=settings.app_version, environment=settings.environment)


@router.get("/db", response_model=HealthStatus, response_model_exclude_none=True, summary="Database connectivity")
async def health_db() -> HealthStatus:
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_SECONDS):
            async with get_engine().connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Database health check failed: %s", type(exc).__name__)
        raise ServiceUnavailableError("DATABASE_UNAVAILABLE", "Ma'lumotlar bazasiga ulanib bo'lmadi.") from exc
    return HealthStatus(status="ok", service="database")


@router.get(
    "/redis",
    response_model=HealthStatus,
    response_model_exclude_none=True,
    summary="Redis connectivity (optional component)",
)
async def health_redis() -> HealthStatus:
    client = get_redis()
    if client is None:
        return HealthStatus(status="not_configured", service="redis")
    try:
        async with asyncio.timeout(_CHECK_TIMEOUT_SECONDS):
            await client.ping()
    except Exception as exc:
        logger.warning("Redis health check failed: %s", type(exc).__name__)
        raise ServiceUnavailableError("REDIS_UNAVAILABLE", "Redis serveriga ulanib bo'lmadi.") from exc
    return HealthStatus(status="ok", service="redis")
