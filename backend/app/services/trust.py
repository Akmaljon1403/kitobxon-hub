"""«🛡 Ishonch markazi»: what may need a second look — never an accusation, only a list to check.

* tests finished very fast with a very high score;
* points changed by hand many times (for a member, or by one admin);
* attendance marked suspicious, and many manual check-ins by one admin;
* unbelievable pages in the reading diary;
* the same bank receipt sent again;
* and a certificate check by its code.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    AttendanceRecord,
    CardPayment,
    Certificate,
    Event,
    ReadingLog,
    ScoreTransaction,
    Test,
    TestAttempt,
    User,
)
from app.models.enums import AttemptStatus, AttendanceMethod, AttendanceStatus, ScoreCategory

DAYS = 30
FAST_SHARE = 0.25  # finished in a quarter of the allowed time…
HIGH_SHARE = 0.9  # …with 90 % of the points or more
MANUAL_PER_MEMBER = 3
MANUAL_PER_ADMIN = 15
MANUAL_CHECKINS_PER_ADMIN = 20
PAGES_A_DAY = 300
LIMIT = 50


def _name(user: User | None) -> str:
    return f"{user.last_name} {user.first_name}".strip() if user else "—"


async def overview(session: AsyncSession, *, days: int = DAYS) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=days)

    seconds = func.extract("epoch", TestAttempt.submitted_at - TestAttempt.started_at)
    fast = (
        await session.execute(
            select(TestAttempt, Test, User, seconds.label("seconds"))
            .join(Test, Test.id == TestAttempt.test_id)
            .join(User, User.id == TestAttempt.user_id)
            .where(
                TestAttempt.status == AttemptStatus.SUBMITTED,
                TestAttempt.submitted_at >= since,
                TestAttempt.score >= Test.max_score * HIGH_SHARE,
                seconds < Test.duration_minutes * 60 * FAST_SHARE,
            )
            .order_by(seconds)
            .limit(LIMIT)
        )
    ).all()

    manual_members = (
        await session.execute(
            select(User, func.count(ScoreTransaction.id), func.sum(ScoreTransaction.amount))
            .join(User, User.id == ScoreTransaction.user_id)
            .where(ScoreTransaction.category == ScoreCategory.MANUAL, ScoreTransaction.created_at >= since)
            .group_by(User.id)
            .having(func.count(ScoreTransaction.id) >= MANUAL_PER_MEMBER)
            .order_by(func.count(ScoreTransaction.id).desc())
            .limit(LIMIT)
        )
    ).all()
    admin = aliased(User)
    manual_admins = (
        await session.execute(
            select(admin, func.count(ScoreTransaction.id), func.sum(ScoreTransaction.amount))
            .join(admin, admin.id == ScoreTransaction.created_by)
            .where(ScoreTransaction.category == ScoreCategory.MANUAL, ScoreTransaction.created_at >= since)
            .group_by(admin.id)
            .having(func.count(ScoreTransaction.id) >= MANUAL_PER_ADMIN)
            .order_by(func.count(ScoreTransaction.id).desc())
        )
    ).all()

    suspicious = (
        await session.execute(
            select(AttendanceRecord, User, Event)
            .join(User, User.id == AttendanceRecord.user_id)
            .join(Event, Event.id == AttendanceRecord.event_id)
            .where(AttendanceRecord.status == AttendanceStatus.SUSPICIOUS, AttendanceRecord.checked_in_at >= since)
            .order_by(AttendanceRecord.checked_in_at.desc())
            .limit(LIMIT)
        )
    ).all()
    checker = aliased(User)
    manual_checkins = (
        await session.execute(
            select(checker, func.count(AttendanceRecord.id))
            .join(checker, checker.id == AttendanceRecord.verified_by)
            .where(AttendanceRecord.method == AttendanceMethod.MANUAL, AttendanceRecord.checked_in_at >= since)
            .group_by(checker.id)
            .having(func.count(AttendanceRecord.id) >= MANUAL_CHECKINS_PER_ADMIN)
            .order_by(func.count(AttendanceRecord.id).desc())
        )
    ).all()

    daily = (
        select(ReadingLog.user_id, ReadingLog.log_date, func.sum(ReadingLog.pages).label("pages"))
        .where(ReadingLog.created_at >= since)
        .group_by(ReadingLog.user_id, ReadingLog.log_date)
        .subquery()
    )
    big_days = (
        await session.execute(
            select(User, daily.c.log_date, daily.c.pages)
            .join(User, User.id == daily.c.user_id)
            .where(daily.c.pages >= PAGES_A_DAY)
            .order_by(daily.c.pages.desc())
            .limit(LIMIT)
        )
    ).all()

    repeated_hashes = (
        select(CardPayment.receipt_sha256)
        .where(CardPayment.receipt_sha256.is_not(None))
        .group_by(CardPayment.receipt_sha256)
        .having(func.count() > 1)
    )
    repeated = (
        await session.execute(
            select(CardPayment, User)
            .join(User, User.id == CardPayment.user_id)
            .where(CardPayment.receipt_sha256.in_(repeated_hashes), CardPayment.created_at >= since)
            .order_by(CardPayment.receipt_sha256, CardPayment.created_at)
            .limit(LIMIT)
        )
    ).all()

    return {
        "days": days,
        "fast_tests": [
            {
                "member": _name(user),
                "test": test.title,
                "score": attempt.score,
                "max_score": test.max_score,
                "seconds": int(spent or 0),
                "allowed_minutes": test.duration_minutes,
                "submitted_at": attempt.submitted_at,
            }
            for attempt, test, user, spent in fast
        ],
        "manual_members": [
            {"member": _name(user), "changes": int(count), "points": int(total or 0)}
            for user, count, total in manual_members
        ],
        "manual_admins": [
            {"admin": _name(user), "changes": int(count), "points": int(total or 0)}
            for user, count, total in manual_admins
        ],
        "suspicious_attendance": [
            {
                "member": _name(user),
                "event": event.title,
                "checked_in_at": record.checked_in_at,
                "method": record.method,
            }
            for record, user, event in suspicious
        ],
        "manual_checkins": [{"admin": _name(user), "count": int(count)} for user, count in manual_checkins],
        "big_reading_days": [{"member": _name(user), "day": day, "pages": int(pages)} for user, day, pages in big_days],
        "repeated_receipts": [
            {
                "member": _name(user),
                "amount_uzs": payment.amount_uzs,
                "status": payment.status,
                "created_at": payment.created_at,
                "group": (payment.receipt_sha256 or "")[:8],
            }
            for payment, user in repeated
        ],
        "thresholds": {
            "fast_share": FAST_SHARE,
            "high_share": HIGH_SHARE,
            "manual_per_member": MANUAL_PER_MEMBER,
            "manual_per_admin": MANUAL_PER_ADMIN,
            "manual_checkins_per_admin": MANUAL_CHECKINS_PER_ADMIN,
            "pages_a_day": PAGES_A_DAY,
        },
    }


async def certificate(session: AsyncSession, code: str) -> dict[str, Any] | None:
    """A certificate by the code printed under its QR code."""
    from app.services.certificates import normalize_code

    cleaned = normalize_code(code)
    row = (
        await session.execute(
            select(Certificate, User)
            .join(User, User.id == Certificate.user_id)
            .where(Certificate.verify_code == cleaned)
        )
    ).first()
    if row is None:
        return None
    cert, user = row
    return {
        "code": cert.verify_code,
        "member": _name(user),
        "title": cert.title,
        "place": cert.place,
        "issued_at": cert.issued_at,
        "valid": cert.revoked_at is None,
        "revoked_at": cert.revoked_at,
        "revoke_reason": cert.revoke_reason,
    }
