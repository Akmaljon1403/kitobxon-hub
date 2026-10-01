"""Public, non-sensitive configuration that the Mini App and Admin Panel need at start-up."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.bot.setup import bot_username
from app.core.config import get_settings

router = APIRouter(prefix="/meta", tags=["meta"])


class PublicMeta(BaseModel):
    app_name: str
    version: str
    bot_username: str | None
    timezone: str


@router.get("", response_model=PublicMeta, summary="Public application information")
async def public_meta() -> PublicMeta:
    settings = get_settings()
    return PublicMeta(
        app_name=settings.app_name,
        version=settings.app_version,
        bot_username=bot_username(),
        timezone=settings.timezone,
    )
