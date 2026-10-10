"""When should the worker look again? The nearest moment something is due.

Without this the worker only woke every ``WORKER_INTERVAL_SECONDS`` (30 minutes on the free
hosting, so the database can sleep), and a channel post, the «test started» message or the
attendance of an event could wait up to half an hour. Now it sleeps exactly until the next
thing that has to happen (but never longer than the interval).
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelPost, Event, EventShift, Giveaway, Notification, Test
from app.models.enums import (
    ChannelPostKind,
    ChannelPostStatus,
    EventStatus,
    GiveawayStatus,
    NotificationStatus,
    TestStatus,
)
from app.services.settings import get_setting
from app.utils.timezone import local_tz

HORIZON = timedelta(days=2)
FEEDBACK_AFTER = timedelta(minutes=30)
CHANNEL_REMINDERS = (timedelta(hours=24), timedelta(hours=3))


async def next_due(session: AsyncSession, now: datetime | None = None) -> datetime | None:
    """The earliest future moment at which a message, a post or a scheduled check is due."""
    now = now or datetime.now(UTC)
    later = now + HORIZON
    review = timedelta(minutes=int(await get_setting(session, "channel.review_minutes") or 0))
    offsets = [timedelta(minutes=m) for m in await get_setting(session, "notifications.event_reminder_minutes")]
    test_ending = timedelta(minutes=int(await get_setting(session, "notifications.test_ending_minutes") or 0))

    published = (Event.status == EventStatus.PUBLISHED, Event.deleted_at.is_(None))
    moments = [
        select(func.min(Notification.scheduled_at)).where(
            Notification.status == NotificationStatus.PENDING, Notification.scheduled_at > now
        ),
        select(func.min(ChannelPost.scheduled_at)).where(
            ChannelPost.status == ChannelPostStatus.PENDING, ChannelPost.scheduled_at > now
        ),
        select(func.min(ChannelPost.scheduled_at - literal(review))).where(
            ChannelPost.status == ChannelPostStatus.PENDING,
            ChannelPost.kind != ChannelPostKind.MANUAL,
            ChannelPost.review_sent_at.is_(None),
            ChannelPost.scheduled_at - literal(review) > now,
        ),
        select(func.min(Event.attendance_opens_at)).where(*published, Event.attendance_opens_at > now),
        select(func.min(EventShift.attendance_opens_at))
        .join(Event, Event.id == EventShift.event_id)
        .where(*published, EventShift.attendance_opens_at > now),
        select(func.min(Event.ends_at)).where(*published, Event.ends_at > now),
        select(func.min(Event.ends_at + literal(FEEDBACK_AFTER))).where(
            Event.deleted_at.is_(None), Event.ends_at + literal(FEEDBACK_AFTER) > now
        ),
        select(func.min(Test.starts_at)).where(
            Test.deleted_at.is_(None), Test.status == TestStatus.PUBLISHED, Test.starts_at > now
        ),
        select(func.min(Test.ends_at)).where(
            Test.deleted_at.is_(None), Test.status == TestStatus.PUBLISHED, Test.ends_at > now
        ),
        select(func.min(Giveaway.scheduled_at)).where(
            Giveaway.status == GiveawayStatus.SCHEDULED, Giveaway.scheduled_at > now
        ),
    ]
    if test_ending:
        moments.append(
            select(func.min(Test.ends_at - literal(test_ending))).where(
                Test.deleted_at.is_(None),
                Test.status == TestStatus.PUBLISHED,
                Test.ends_at - literal(test_ending) > now,
            )
        )
    for offset in [*offsets, *CHANNEL_REMINDERS]:
        moments.append(
            select(func.min(Event.starts_at - literal(offset))).where(
                *published, Event.starts_at - literal(offset) > now, Event.starts_at < later
            )
        )
        moments.append(
            select(func.min(EventShift.starts_at - literal(offset)))
            .join(Event, Event.id == EventShift.event_id)
            .where(*published, EventShift.starts_at - literal(offset) > now, EventShift.starts_at < later)
        )
    rows = (await session.execute(union_all(*moments))).scalars().all()
    upcoming = [moment for moment in rows if moment is not None]
    hour, minute = (int(part) for part in str(await get_setting(session, "notifications.quote_of_day_time")).split(":"))
    local = now.astimezone(local_tz())
    quote_at = datetime.combine(local.date(), time(hour, minute), tzinfo=local_tz())
    if quote_at <= now:
        quote_at += timedelta(days=1)
    upcoming.append(quote_at.astimezone(UTC))
    return min(upcoming)


async def seconds_until_due(session: AsyncSession) -> float | None:
    moment = await next_due(session)
    if moment is None:
        return None
    return max((moment - datetime.now(UTC)).total_seconds(), 0.0)
