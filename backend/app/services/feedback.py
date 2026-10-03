"""Event feedback (⭐ 1-5 and an optional comment) and the weekly personal digest."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import AttendanceRecord, Event, EventFeedback, ScoreTransaction, User
from app.models.enums import AttendanceStatus, EventStatus, NotificationType
from app.services import features
from app.services.notifications import enqueue_for_members, enqueue_notification, render
from app.utils.timezone import format_human, local_tz

ASK_AFTER = timedelta(minutes=30)  # after the event's end
ASK_WITHIN = timedelta(days=1)  # older events are not asked about any more
MAX_COMMENT = 1000


def stars_row(event_id: uuid.UUID) -> dict[str, Any]:
    """One keyboard row of five star buttons (the sender keeps a "row" on one line)."""
    return {"row": [{"text": f"{n}⭐", "callback": f"fb:{event_id.hex}:{n}"} for n in range(1, 6)]}


async def request_feedback(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: ask members who attended an event that ended a little earlier."""
    members = await features.recipients(session, "event_feedback")
    if members is None:
        return 0
    now = now or datetime.now(UTC)
    events = list(
        await session.scalars(
            select(Event).where(
                Event.deleted_at.is_(None),
                Event.status.in_((EventStatus.PUBLISHED, EventStatus.COMPLETED)),
                Event.ends_at <= now - ASK_AFTER,
                Event.ends_at > now - ASK_WITHIN,
            )
        )
    )
    queued = 0
    for event in events:
        text = await render(session, NotificationType.FEEDBACK_REQUEST, event_title=event.title)
        if text is None:
            return 0
        attended = select(AttendanceRecord.user_id).where(
            AttendanceRecord.event_id == event.id, AttendanceRecord.status == AttendanceStatus.VERIFIED
        )
        queued += await enqueue_for_members(
            session,
            type_=NotificationType.FEEDBACK_REQUEST,
            text=text,
            dedup_prefix=f"feedback:{event.id}",
            members=members.where(User.id.in_(attended)),
            payload={"buttons": [stars_row(event.id)]},
            priority=6,
        )
    return queued


async def _attended(session: AsyncSession, event_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(func.count())
            .select_from(AttendanceRecord)
            .where(
                AttendanceRecord.event_id == event_id,
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.status == AttendanceStatus.VERIFIED,
            )
        )
    )


async def rate(
    session: AsyncSession, *, user: User, event_id: uuid.UUID, rating: int, comment: str | None = None
) -> EventFeedback:
    """Save (or change) the member's rating; a comment, if given, replaces the old one."""
    await features.require(session, user, "event_feedback")
    event = await session.get(Event, event_id)
    if event is None or event.deleted_at is not None:
        raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
    if not await _attended(session, event_id, user.id):
        raise ConflictError("NOT_ATTENDED", "Baho faqat tadbirda qatnashganlar uchun.")
    values: dict[str, Any] = {"event_id": event_id, "user_id": user.id, "rating": rating}
    update: dict[str, Any] = {"rating": rating, "updated_at": func.now()}
    if comment is not None:
        values["comment"] = comment.strip()[:MAX_COMMENT] or None
        update["comment"] = values["comment"]
    await session.execute(
        insert(EventFeedback)
        .values(**values)
        .on_conflict_do_update(index_elements=[EventFeedback.event_id, EventFeedback.user_id], set_=update)
    )
    await session.commit()
    feedback = await session.scalar(
        select(EventFeedback).where(EventFeedback.event_id == event_id, EventFeedback.user_id == user.id)
    )
    assert feedback is not None
    return feedback


async def add_comment(session: AsyncSession, *, user: User, event_id: uuid.UUID, comment: str) -> EventFeedback:
    feedback = await session.scalar(
        select(EventFeedback).where(EventFeedback.event_id == event_id, EventFeedback.user_id == user.id)
    )
    if feedback is None:
        raise NotFoundError("FEEDBACK_NOT_FOUND", "Avval tadbirga baho bering.")
    feedback.comment = comment.strip()[:MAX_COMMENT] or None
    await session.commit()
    return feedback


async def my_feedback(session: AsyncSession, *, user_id: uuid.UUID, event_id: uuid.UUID) -> EventFeedback | None:
    return await session.scalar(
        select(EventFeedback).where(EventFeedback.event_id == event_id, EventFeedback.user_id == user_id)
    )


async def summary(session: AsyncSession, event_id: uuid.UUID, *, with_comments: bool = True) -> dict[str, Any]:
    """Average, distribution and comments (with names: only administrators see this)."""
    rows = (
        await session.execute(
            select(EventFeedback, User.first_name, User.last_name)
            .join(User, User.id == EventFeedback.user_id)
            .where(EventFeedback.event_id == event_id)
            .order_by(EventFeedback.updated_at.desc())
        )
    ).all()
    ratings = [row[0].rating for row in rows]
    return {
        "count": len(ratings),
        "average": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "distribution": {str(n): ratings.count(n) for n in range(1, 6)},
        "comments": [
            {
                "rating": feedback.rating,
                "comment": feedback.comment,
                "name": f"{first} {last}",
                "updated_at": feedback.updated_at,
            }
            for feedback, first, last in rows
            if feedback.comment
        ]
        if with_comments
        else [],
    }


# ---------------------------------------------------------------------------- weekly digest


async def weekly_digest(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: on Monday from 09:00, a personal summary of the past week."""
    from app.services.ranking import ranking

    local_now = (now or datetime.now(UTC)).astimezone(local_tz())
    if local_now.weekday() != 0 or local_now.time() < time(9, 0) or local_now.time() > time(21, 0):
        return 0
    members = await features.recipients(session, "weekly_digest")
    if members is None:
        return 0
    recipients = list(await session.scalars(members))
    if not recipients:
        return 0
    week_start = datetime.combine(local_now.date() - timedelta(days=7), time.min, tzinfo=local_tz())
    week_end = datetime.combine(local_now.date(), time.min, tzinfo=local_tz())
    weekly = dict(
        (
            await session.execute(
                select(ScoreTransaction.user_id, func.sum(ScoreTransaction.amount))
                .where(
                    ScoreTransaction.user_id.in_(recipients),
                    ScoreTransaction.created_at >= week_start,
                    ScoreTransaction.created_at < week_end,
                )
                .group_by(ScoreTransaction.user_id)
            )
        ).all()
    )
    board = await ranking(session, period="all", scope="all", viewer=None, limit=100_000)
    places = {row.user_id: (row.rank, row.total) for row in board.items}
    next_event = await session.scalar(
        select(Event)
        .where(Event.deleted_at.is_(None), Event.status == EventStatus.PUBLISHED, Event.starts_at > local_now)
        .order_by(Event.starts_at)
        .limit(1)
    )
    week_label = f"{local_now:%G-W%V}"
    queued = 0
    for user_id in recipients:
        rank, total = places.get(user_id, (None, 0))
        lines = [  # plain text: the template adds the heading and escapes these values
            f"O'tgan hafta: +{int(weekly.get(user_id) or 0)} ball",
            f"Jami: {total} ball" + (f" · reytingda {rank}-o'rin" if rank else ""),
        ]
        if next_event is not None:
            lines.append(f"📅 Keyingi tadbir: «{next_event.title}» — {format_human(next_event.starts_at)}")
        text = await render(session, NotificationType.DIGEST, message="\n".join(lines))
        if text is None:
            return queued
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.DIGEST,
            text=text,
            dedup_key=f"digest:{week_label}:{user_id}",
            payload={"buttons": [{"text": "📊 Natijalarim", "app_route": "results"}]},
            priority=7,
        )
        queued += 1
    return queued
