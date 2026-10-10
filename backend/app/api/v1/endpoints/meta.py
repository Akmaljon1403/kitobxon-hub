"""Public, non-sensitive configuration that the Mini App and Admin Panel need at start-up."""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.api.deps import DbSession
from app.bot.setup import bot_username
from app.core.config import get_settings
from app.core.errors import NotFoundError

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


class DesignItem(BaseModel):
    code: str
    title: str


@router.get(
    "/certificate-designs",
    response_model=list[DesignItem],
    summary="The standard certificate designs, in the order they take turns",
)
async def certificate_design_list() -> list[DesignItem]:
    from app.services import certificates as certificate_service

    return [DesignItem(**item) for item in certificate_service.design_list()]


@router.get(
    "/certificate-designs/{code}.png",
    summary="A sample picture of a certificate design (cached)",
    response_class=Response,
)
async def certificate_design_picture(code: str, db: DbSession) -> Response:
    from app.services import certificate_designs
    from app.services import certificates as certificate_service

    if code not in certificate_designs.BY_CODE:
        raise NotFoundError("DESIGN_NOT_FOUND", "Bunday dizayn yo'q.")
    data = await certificate_service.design_thumbnail(db, code)
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
