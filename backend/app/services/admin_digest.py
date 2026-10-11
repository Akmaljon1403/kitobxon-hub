"""«🌅 Xayrli tong»: every morning the club's owners get one short message with what waits for them
(new members, receipts, questions, manual attendance to approve) and what happens today."""

from __future__ import annotations

import html
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    AttendanceRecord,
    CardPayment,
    Event,
    ReferralContest,
    Role,
    SupportTicket,
    Test,
    User,
    UserRole,
)
from app.models.enums import (
    AttendanceStatus,
    CardPaymentStatus,
    ContestStatus,
    EventStatus,
    NotificationType,
    TestStatus,
    UserStatus,
)
from app.services import payments_chat
from app.services.notifications import enqueue_notification
from app.services.settings import get_setting
from app.utils.timezone import local_tz


def _e(value: str) -> str:
    return html.escape(value, quote=False)


async def _count(session: AsyncSession, query: object) -> int:
    return int(await session.scalar(query) or 0)  # type: ignore[arg-type]


async def text(session: AsyncSession, now: datetime) -> str:
    local = now.astimezone(local_tz())
    today_start = datetime.combine(local.date(), time.min, tzinfo=local_tz())
    tomorrow = today_start + timedelta(days=1)
    yesterday = today_start - timedelta(days=1)
    active = await _count(
        session,
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None)),
    )
    joined = await _count(
        session,
        select(func.count(User.id)).where(
            User.registered_at >= yesterday, User.registered_at < today_start, User.deleted_at.is_(None)
        ),
    )
    waiting_members = await _count(
        session,
        select(func.count(User.id)).where(User.status == UserStatus.PENDING, User.deleted_at.is_(None)),
    )
    receipts = await _count(
        session, select(func.count(CardPayment.id)).where(CardPayment.status == CardPaymentStatus.PENDING)
    )
    questions = await _count(
        session, select(func.count(SupportTicket.id)).where(SupportTicket.unread_for_admin.is_(True))
    )
    manual = await _count(
        session, select(func.count(AttendanceRecord.id)).where(AttendanceRecord.status == AttendanceStatus.PENDING)
    )
    events = list(
        await session.execute(
            select(Event.title, Event.starts_at)
            .where(
                Event.deleted_at.is_(None),
                Event.status == EventStatus.PUBLISHED,
                Event.starts_at >= today_start,
                Event.starts_at < tomorrow,
            )
            .order_by(Event.starts_at)
        )
    )
    tests = list(
        await session.scalars(
            select(Test.title).where(
                Test.deleted_at.is_(None),
                Test.status == TestStatus.PUBLISHED,
                Test.ends_at >= now,
                Test.ends_at < tomorrow,
            )
        )
    )
    contests = list(
        await session.execute(
            select(ReferralContest.title, ReferralContest.ends_at).where(
                ReferralContest.status == ContestStatus.PUBLISHED,
                ReferralContest.starts_at <= now,
                ReferralContest.ends_at > now,
            )
        )
    )

    lines = ["🌅 <b>Xayrli tong! Klub holati</b>", ""]
    lines.append(f"👥 Faol a'zolar: <b>{active}</b>" + (f" (kecha +{joined})" if joined else ""))
    todo = []
    if waiting_members:
        todo.append(f"⏳ Tasdiq kutayotgan a'zolar: <b>{waiting_members}</b>")
    if receipts and not await payments_chat.chat_id(session):  # with a payments channel, they are recalled there
        todo.append(f"🧾 Tekshirilmagan to'lov cheklari: <b>{receipts}</b>")
    if questions:
        todo.append(f"📨 Javob kutayotgan murojaatlar: <b>{questions}</b>")
    if manual:
        todo.append(f"✅ Tasdiq kutayotgan qo'lda davomat: <b>{manual}</b>")
    if todo:
        lines += ["", "<b>Sizni kutmoqda:</b>", *todo]
    today = [f"📅 {starts.astimezone(local_tz()):%H:%M} — {_e(title)}" for title, starts in events] + [
        f"📝 Bugun tugaydi: {_e(title)}" for title in tests
    ]
    today += [
        f"🏁 Tanlov davom etmoqda: {_e(title)} ({ends.astimezone(local_tz()):%d.%m} gacha)" for title, ends in contests
    ]
    if today:
        lines += ["", "<b>Bugun:</b>", *today]
    if not todo and not today:
        lines += ["", "Hammasi joyida — kutayotgan ish yo'q ☕"]
    return "\n".join(lines)


async def send(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job (08:00): the morning message to every super administrator."""
    if not await get_setting(session, "admin.morning_digest"):
        return 0
    now = now or datetime.now(UTC)
    owners = list(
        await session.scalars(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.code == "SUPER_ADMIN", User.deleted_at.is_(None), User.status == UserStatus.ACTIVE)
        )
    )
    if not owners:
        return 0
    body = await text(session, now)
    base = get_settings().base_url
    payload = {"buttons": [{"text": "🛠 Admin panel", "url": f"{base}/admin/"}]} if base else None
    day = now.astimezone(local_tz()).date().isoformat()
    for user_id in owners:
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.SYSTEM,
            text=body,
            dedup_key=f"admin-digest:{day}:{user_id}",
            payload=payload,
            priority=2,
        )
    await session.commit()
    return len(owners)
