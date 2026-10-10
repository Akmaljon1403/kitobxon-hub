"""Scheduled checks. Each runs in its own transaction under a PostgreSQL advisory lock, so
several running workers never do the same job at the same time. Every job is also idempotent
(dedup keys, "already awarded" markers), so running it twice is harmless."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import achievements, announcements, channel, membership
from app.services import attendance as attendance_service
from app.services import certificates as certificate_service
from app.services import events as event_service
from app.services import feedback as feedback_service
from app.services import giveaways as giveaway_service
from app.services import premium as premium_service
from app.services import quizzes as quiz_service

logger = logging.getLogger(__name__)

LOCK_NAMESPACE = 0x4B48  # "KH"
Job = Callable[[AsyncSession], Awaitable[int]]

JOBS: tuple[tuple[str, Job], ...] = (
    ("close_ended_tests", quiz_service.close_ended_tests),
    ("event_reminders", announcements.event_reminders),
    ("test_started", announcements.test_started),
    ("test_ending", announcements.test_ending),
    ("reading_reminders", announcements.reading_reminders),
    ("quote_of_day", announcements.quote_of_day),
    ("achievements_safety_net", achievements.evaluate_recently_active),
    ("monthly_top_ranks", achievements.monthly_top_ranks),
    # New jobs go last: the position is part of each job's lock id.
    ("attendance_auto_open", attendance_service.open_scheduled_sessions),
    ("monthly_certificates", certificate_service.issue_monthly),
    ("event_feedback_requests", feedback_service.request_feedback),
    ("weekly_digest", feedback_service.weekly_digest),
    ("giveaways_due", giveaway_service.run_due),
    ("channel_posts", channel.scheduled_posts),
    ("premium_reminders", premium_service.remind_expiring),
    ("erase_left_members", membership.erase_expired),
    ("complete_events", event_service.complete_finished),
)


async def run_scheduled_jobs(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, int]:
    """Run every job once. A failing job is logged and does not stop the others."""
    results: dict[str, int] = {}
    for index, (name, job) in enumerate(JOBS):
        async with session_factory() as session:
            try:
                locked = await session.scalar(select(func.pg_try_advisory_xact_lock(LOCK_NAMESPACE, index)))
                if not locked:
                    continue  # another worker is running this job right now
                results[name] = await job(session)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Scheduled job %s failed", name)
    done = {name: count for name, count in results.items() if count}
    if done:
        logger.info("Scheduled jobs: %s", done)
    return results
