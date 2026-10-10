"""Admin Panel: messages to members and the state of the notification queue."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.core.config import get_settings
from app.models import AuditLog, User
from app.schemas.notification import (
    BroadcastHistoryItem,
    BroadcastIn,
    BroadcastOut,
    BroadcastPreviewOut,
    NotificationSummaryOut,
)
from app.security.permissions import Perm
from app.services import announcements
from app.services.notifications import queue_summary

router = APIRouter(prefix="/admin/notifications", tags=["admin: notifications"])
Sender = Annotated[CurrentUser, Depends(require_permissions(Perm.NOTIFICATION_SEND))]


@router.get("/summary", response_model=NotificationSummaryOut, summary="Queue state and recent broadcasts")
async def summary(_: Sender, db: DbSession) -> NotificationSummaryOut:
    settings = get_settings()
    rows = await db.execute(
        select(AuditLog, User.first_name, User.last_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.action == "NOTIFICATION_BROADCAST")
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    history = []
    for entry, first, last in rows:
        after = entry.after or {}
        history.append(
            BroadcastHistoryItem(
                at=entry.created_at,
                actor=f"{first} {last}" if first else None,
                message=after.get("message", ""),
                recipients=int(after.get("recipients", 0)),
                filters={key: after.get(key) for key in ("faculty_id", "course", "group_name") if after.get(key)},
            )
        )
    return NotificationSummaryOut(
        **await queue_summary(db),
        worker_enabled=settings.worker_enabled,
        bot_configured=settings.bot_enabled,
        recent_broadcasts=history,
    )


@router.post("/broadcast", response_model=BroadcastOut, summary="Send a message to members (or count recipients)")
async def broadcast(payload: BroadcastIn, current: Sender, db: DbSession) -> BroadcastOut:
    recipients = await announcements.broadcast(
        db,
        actor_id=current.user.id,
        message=payload.message,
        faculty_id=payload.faculty_id,
        course=payload.course,
        group_name=payload.group_name,
        with_app_button=payload.with_app_button,
        buttons=payload.buttons,
        dry_run=payload.dry_run,
        only_to=current.user.id if payload.test else None,
    )
    return BroadcastOut(recipients=recipients, queued=not payload.dry_run)


@router.post(
    "/broadcast/preview", response_model=BroadcastPreviewOut, summary="How the message will look, and to how many"
)
async def broadcast_preview(payload: BroadcastIn, _: Sender, db: DbSession) -> BroadcastPreviewOut:
    text, buttons = await announcements.broadcast_message(
        db, message=payload.message, buttons=payload.buttons, with_app_button=payload.with_app_button
    )
    recipients = await announcements.broadcast(
        db,
        actor_id=None,
        message=payload.message,
        faculty_id=payload.faculty_id,
        course=payload.course,
        group_name=payload.group_name,
        with_app_button=payload.with_app_button,
        buttons=payload.buttons,
        dry_run=True,
    )
    shown = [
        {"text": spec["text"], "url": spec.get("url") or "", "kind": "url" if spec.get("url") else "app"}
        for spec in (buttons or {}).get("buttons", [])
    ]
    return BroadcastPreviewOut(text=text, buttons=shown, recipients=recipients)
