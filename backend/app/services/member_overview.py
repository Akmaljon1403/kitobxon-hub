"""Admin Panel: one member's whole picture in a single place (Q12).

A quick snapshot an administrator can read at a glance — points and their breakdown, how active the
member is (attendance, tests, books, reading diary, saved quotes), their premium state, how many friends
they brought, and whether they have open questions. Every number reuses the same queries the rest of the
app already trusts, so the snapshot never drifts from the sections it summarises.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttendanceRecord,
    BookRead,
    ReadingLog,
    SavedQuote,
    SupportTicket,
    TestAttempt,
    User,
    UserAchievement,
)
from app.models.enums import AttemptStatus, AttendanceStatus, ReadingStatus, SupportTicketStatus
from app.services import premium
from app.services import ranking as ranking_service

FINISHED = (AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)


async def _count(session: AsyncSession, condition: Any, model: Any) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(condition)) or 0)


async def overview(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Aggregated figures for one member — safe to call for any member id."""
    scores = await ranking_service.score_summary(session, user_id)
    return {
        "points": scores,  # {"total", "breakdown", "season"}
        "attendance": await _count(
            session,
            (AttendanceRecord.user_id == user_id) & (AttendanceRecord.status == AttendanceStatus.VERIFIED),
            AttendanceRecord,
        ),
        "tests_taken": int(
            await session.scalar(
                select(func.count(func.distinct(TestAttempt.id))).where(
                    TestAttempt.user_id == user_id, TestAttempt.status.in_(FINISHED)
                )
            )
            or 0
        ),
        "books_completed": await _count(
            session, (BookRead.user_id == user_id) & (BookRead.status == ReadingStatus.COMPLETED), BookRead
        ),
        "support": {
            "total": await _count(session, SupportTicket.user_id == user_id, SupportTicket),
            "open": await _count(
                session,
                (SupportTicket.user_id == user_id) & (SupportTicket.status != SupportTicketStatus.CLOSED),
                SupportTicket,
            ),
        },
        "referrals": await _count(session, (User.referred_by == user_id) & (User.deleted_at.is_(None)), User),
        "achievements": await _count(session, UserAchievement.user_id == user_id, UserAchievement),
        "reading": {
            "diary_entries": await _count(session, ReadingLog.user_id == user_id, ReadingLog),
            "saved_quotes": await _count(session, SavedQuote.user_id == user_id, SavedQuote),
        },
        "premium_until": await premium.premium_until(session, user_id),
    }
