"""Admin Panel: «📝 Matnlar» — the bot's messages, the member notifications and the channel's phrases, in the
owner's own words (several variants each, sent in turn)."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, SuperAdminDep, require_permissions
from app.security.permissions import Perm
from app.services import delivery, texts_admin
from app.services.settings import get_setting

router = APIRouter(prefix="/admin/texts", tags=["admin: texts"])
Editor = Annotated[CurrentUser, Depends(require_permissions(Perm.TEXTS_MANAGE))]


class TextOut(BaseModel):
    key: str
    kind: str
    group: str
    title: str
    default: str
    defaults: list[str] | None = None
    builtin: list[str]
    allowed: list[str]
    variants: list[str] | None
    rotate: bool
    active: bool | None = None
    hint: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


class TextsOut(BaseModel):
    rotation: bool
    items: list[TextOut]


class TextIn(BaseModel):
    variants: list[str] = Field(min_length=1, max_length=texts_admin.MAX_VARIANTS)
    rotate: bool = True


class ActiveIn(BaseModel):
    active: bool


class PreviewIn(BaseModel):
    text: str = Field(min_length=1, max_length=texts_admin.MAX_LENGTH)


@router.get("", response_model=TextsOut, summary="Every editable text with the owner's edits")
async def list_texts(_: Editor, db: DbSession) -> TextsOut:
    return TextsOut(
        rotation=bool(await get_setting(db, "texts.rotate")),
        items=[TextOut(**item) for item in await texts_admin.catalogue(db)],
    )


@router.put("/{key}", response_model=dict[str, bool], summary="Save the owner's wording (one or more variants)")
async def save_text(key: str, payload: TextIn, current: Editor, db: DbSession) -> dict[str, bool]:
    await texts_admin.save(db, actor_id=current.user.id, key=key, variants=payload.variants, rotate=payload.rotate)
    return {"saved": True}


@router.delete("/{key}", response_model=dict[str, bool], summary="Back to the built-in wording")
async def reset_text(key: str, current: Editor, db: DbSession) -> dict[str, bool]:
    await texts_admin.reset(db, actor_id=current.user.id, key=key)
    return {"reset": True}


@router.put("/{key}/active", response_model=dict[str, bool], summary="Switch a member notification on or off")
async def switch_notification(key: str, payload: ActiveIn, current: Editor, db: DbSession) -> dict[str, bool]:
    await texts_admin.set_active(db, actor_id=current.user.id, key=key, active=payload.active)
    return {"active": payload.active}


@router.post("/{key}/check", response_model=dict[str, Any], summary="Check a variant without saving it")
async def check_text(key: str, payload: PreviewIn, _: Editor, db: DbSession) -> dict[str, Any]:
    item = texts_admin._find(key)
    problems = texts_admin.check(payload.text, set(item["allowed"]), braces=item["braces"])
    return {"ok": not problems, "problems": problems}


@router.post("/{key}/preview", response_model=dict[str, bool], summary="The bot shows me how it looks")
async def preview_text(key: str, payload: PreviewIn, current: Editor, db: DbSession) -> dict[str, bool]:
    item = texts_admin._find(key)
    problems = texts_admin.check(payload.text, set(item["allowed"]), braces=item["braces"])
    if problems:
        from app.core.errors import BadRequestError

        raise BadRequestError("TEXT_INVALID", "; ".join(problems))
    head = f"👀 <b>Namuna</b> — «{html.escape(item['title'], quote=False)}»\n\n"
    await delivery.explain_failures(
        delivery.runtime_bot().send_message(current.user.telegram_id, head + texts_admin.sample(payload.text))
    )
    return {"sent": True}


@router.get("/export/all", response_model=dict[str, Any], summary="All edits as a file (a backup)")
async def export_texts(_: Editor, db: DbSession) -> dict[str, Any]:
    return await texts_admin.export(db)


@router.post("/import/all", response_model=dict[str, Any], summary="Bring saved edits back")
async def import_texts(payload: dict[str, Any], current: Editor, db: DbSession) -> dict[str, Any]:
    return await texts_admin.import_(db, actor_id=current.user.id, data=payload)


# ---------------------------------------------------------------------------- «🛰 Nazorat markazi»

control_router = APIRouter(prefix="/admin/control", tags=["admin: control"])


@control_router.get("", response_model=dict[str, Any], summary="Every queue, who did what — the super admin's view")
async def control_centre(_: SuperAdminDep, db: DbSession) -> dict[str, Any]:
    from app.services import control

    return await control.overview(db)
