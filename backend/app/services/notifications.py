"""Outgoing notification queue (outbox).

Business code only *enqueues* messages here, inside its own transaction. The background
sender delivers them with throttling and retries, so a mass notification never blocks an
HTTP request and a message is never lost when Telegram is temporarily unavailable.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification
from app.models.enums import NotificationType


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
