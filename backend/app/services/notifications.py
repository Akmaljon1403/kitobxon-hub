"""Outgoing notification queue (outbox).

Business code only *enqueues* messages here, inside its own transaction. The background
sender (``app.workers.sender``) delivers them with throttling and retries, so a mass
notification never blocks an HTTP request and a message is never lost when Telegram is
temporarily unavailable. Every message has a dedup key, so retries and repeated scheduler
runs never send the same reminder twice.
"""

from __future__ import annotations

import asyncio
import html
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, literal, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, NotificationTemplate, User
from app.models.enums import NotificationStatus, NotificationType, UserStatus

# Which member preference switches each non-critical type off (see /settings in the bot).
PREFERENCE_FIELD: dict[NotificationType, str] = {
    NotificationType.EVENT_CREATED: "event_reminders",
    NotificationType.EVENT_REMINDER: "event_reminders",
    NotificationType.EVENT_STARTED: "event_reminders",
    NotificationType.ATTENDANCE_OPEN: "event_reminders",
    NotificationType.TEST_STARTED: "test_reminders",
    NotificationType.TEST_ENDING: "test_reminders",
    NotificationType.NEW_BOOK: "reading_reminders",
    NotificationType.READING_REMINDER: "reading_reminders",
    NotificationType.QUOTE_OF_DAY: "quote_of_day",
    NotificationType.RANKING_UPDATE: "ranking_updates",
    NotificationType.ACHIEVEMENT_UNLOCKED: "achievement_alerts",
}
# Time-sensitive reminders that are pointless after a long outage (e.g. a sleeping free server).
STALE_AFTER: dict[NotificationType, timedelta] = {
    NotificationType.ATTENDANCE_OPEN: timedelta(hours=1),
    NotificationType.EVENT_STARTED: timedelta(hours=1),
    NotificationType.EVENT_REMINDER: timedelta(hours=3),
    NotificationType.TEST_ENDING: timedelta(hours=3),
    NotificationType.TEST_STARTED: timedelta(hours=24),
    NotificationType.QUOTE_OF_DAY: timedelta(hours=12),
    NotificationType.READING_REMINDER: timedelta(hours=24),
    NotificationType.EVENT_CREATED: timedelta(hours=24),
    NotificationType.NEW_BOOK: timedelta(hours=48),
}

# Wakes the in-process sender right after something was queued (no waiting for the next poll).
_wake: asyncio.Event | None = None
_wake_loop: asyncio.AbstractEventLoop | None = None


def wake_sender() -> None:
    if _wake is not None:
        _wake.set()


async def wait_for_work(seconds: float) -> bool:
    """Sleep up to ``seconds``, or less if this process queued a message meanwhile.

    Returns True when woken early by a new message."""
    global _wake, _wake_loop
    loop = asyncio.get_running_loop()
    if _wake is None or _wake_loop is not loop:
        _wake, _wake_loop = asyncio.Event(), loop
    try:
        await asyncio.wait_for(_wake.wait(), seconds)
        woken = True
    except TimeoutError:
        woken = False
    _wake.clear()
    return woken


class _Values(defaultdict[str, str]):
    """Missing template placeholders render as an empty string instead of failing."""

    def __missing__(self, key: str) -> str:
        return ""


async def render(session: AsyncSession, type_: NotificationType, **values: Any) -> str | None:
    """Text from the admin-editable template, or None when that template is switched off.

    Values are HTML-escaped because the bot sends messages in HTML mode.
    """
    template = await session.scalar(select(NotificationTemplate).where(NotificationTemplate.type == type_))
    if template is None or not template.is_active:
        return None
    safe = _Values(
        str, {key: html.escape(str(value), quote=False) if value is not None else "—" for key, value in values.items()}
    )
    return template.body.format_map(safe).strip()


def app_button(route: str, text: str = "📱 Ilovada ochish") -> dict[str, Any]:
    """Payload for an inline button that opens a Mini App page (e.g. ``events/<id>``)."""
    return {"buttons": [{"text": text, "app_route": route}]}


async def enqueue_notification(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    type_: NotificationType,
    text: str,
    dedup_key: str | None = None,
    payload: dict[str, Any] | None = None,
    priority: int = 5,
    scheduled_at: datetime | None = None,
) -> None:
    values: dict[str, Any] = {
        "user_id": user_id,
        "type": type_,
        "text": text,
        "dedup_key": dedup_key,
        "payload": payload,
        "priority": priority,
    }
    if scheduled_at is not None:
        values["scheduled_at"] = scheduled_at
    statement = insert(Notification).values(**values)
    if dedup_key is not None:
        statement = statement.on_conflict_do_nothing(index_elements=[Notification.dedup_key])
    await session.execute(statement)
    wake_sender()


def active_members() -> Select[tuple[uuid.UUID]]:
    return select(User.id).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))


async def enqueue_for_members(
    session: AsyncSession,
    *,
    type_: NotificationType,
    text: str,
    dedup_prefix: str,
    members: Select[tuple[uuid.UUID]] | None = None,
    payload: dict[str, Any] | None = None,
    priority: int = 5,
) -> int:
    """Queue the same message for many members in one statement. Returns how many were new.

    ``members`` is a SELECT of user ids (default: every active member). The dedup key is
    ``<dedup_prefix>:<user id>``, so calling this again never duplicates a message.
    """
    recipients = (members if members is not None else active_members()).subquery()
    source = select(
        recipients.c.id,
        literal(type_.value),
        literal(text),
        literal(payload, JSONB) if payload is not None else literal(None, JSONB),
        literal(priority),
        func.concat(dedup_prefix, ":", recipients.c.id),
    )
    statement = (
        insert(Notification)
        # Python-side defaults would give every row the same id; let the database fill them in.
        .from_select(["user_id", "type", "text", "payload", "priority", "dedup_key"], source, include_defaults=False)
        .on_conflict_do_nothing(index_elements=[Notification.dedup_key])
    )
    result = await session.execute(statement)
    wake_sender()
    return int(result.rowcount or 0)


async def queue_summary(session: AsyncSession) -> dict[str, int]:
    """Counts for the Admin Panel: what is waiting and what happened in the last 24 hours."""
    since = datetime.now(UTC) - timedelta(hours=24)
    pending = await session.scalar(
        select(func.count()).select_from(Notification).where(Notification.status == NotificationStatus.PENDING)
    )
    rows = await session.execute(
        select(Notification.status, func.count())
        .where(Notification.updated_at >= since, Notification.status != NotificationStatus.PENDING)
        .group_by(Notification.status)
    )
    recent = {status.value if hasattr(status, "value") else str(status): int(count) for status, count in rows}
    return {
        "pending": int(pending or 0),
        "sent_24h": recent.get("SENT", 0),
        "failed_24h": recent.get("FAILED", 0),
        "skipped_24h": recent.get("SKIPPED", 0),
    }
