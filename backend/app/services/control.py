"""«🛰 Nazorat markazi» — the super admin's view of every process at once: what is waiting and for how long,
who did what lately, and a link to step in anywhere.

Nothing here decides anything: it only counts. Each line leads to the page where the super admin (who holds
every right) acts — and every copy in the admins' chats then shows the decision (``copies``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttendanceRecord,
    AuditLog,
    CardPayment,
    ChannelPost,
    Contribution,
    SupportMessage,
    SupportTicket,
    User,
)
from app.models.enums import (
    AttendanceStatus,
    CardPaymentStatus,
    ChannelPostStatus,
    ContributionStatus,
    PaymentKind,
    SupportTicketStatus,
    UserStatus,
)
from app.services.notifications import queue_summary

# Audit actions in the owner's words (the rest are shown as they are).
ACTIONS: dict[str, str] = {
    "SUPPORT_REPLY": "murojaatga javob berdi",
    "SUPPORT_STATUS": "murojaat holatini o'zgartirdi",
    "CARD_PAYMENT_APPROVE": "to'lovni tasdiqladi",
    "CARD_PAYMENT_REJECT": "to'lovni rad etdi",
    "CARD_PAYMENT_UNDO": "to'lov qarorini qaytardi",
    "CARD_STARS_DELIVERED": "Stars yubordi",
    "CONTRIBUTION_APPROVE": "a'zo fikrini lentaga chiqardi",
    "CONTRIBUTION_FEATURE": "a'zo fikrini tanladi",
    "CONTRIBUTION_HIDE": "a'zo fikrini yashirdi",
    "ATTENDANCE_MANUAL_APPROVE": "qo'lda davomatni tasdiqladi",
    "ATTENDANCE_MANUAL_REJECT": "qo'lda davomatni rad etdi",
    "CHANNEL_POST_APPROVE": "kanal postini tasdiqladi",
    "CHANNEL_POST_CANCEL": "kanal postini bekor qildi",
    "CHANNEL_POST_EDIT": "kanal postini tahrirladi",
    "CHANNEL_POST": "kanalga post yubordi",
    "TEXT_EDIT": "bot matnini o'zgartirdi",
    "TEXT_RESET": "bot matnini asliga qaytardi",
    "SETTING_UPDATE": "sozlamani o'zgartirdi",
    "SCORE_ADJUST": "ballni qo'lda o'zgartirdi",
    "PREMIUM_GRANT": "Premium sovg'a qildi",
    "MEMBERSHIP_RESTORED": "a'zolikni tikladi",
    "USER_BLOCK": "a'zoni blokladi",
    "TEST_PUBLISH": "testni e'lon qildi",
    "EVENT_CREATE": "tadbir yaratdi",
    "BOOK_CREATE": "kitob qo'shdi",
}


def _age(moment: datetime | None, now: datetime) -> int | None:
    """How many minutes something has been waiting."""
    if moment is None:
        return None
    return max(0, int((now - moment).total_seconds() // 60))


async def overview(session: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)

    async def waiting(model: Any, *conditions: Any, at: Any) -> tuple[int, int | None]:
        count, oldest = (await session.execute(select(func.count(), func.min(at)).where(*conditions))).one()
        return int(count or 0), _age(oldest, now)

    tickets = await waiting(
        SupportTicket, SupportTicket.status == SupportTicketStatus.OPEN, at=SupportTicket.last_message_at
    )
    receipts = await waiting(CardPayment, CardPayment.status == CardPaymentStatus.PENDING, at=CardPayment.created_at)
    stars = await waiting(
        CardPayment,
        CardPayment.kind == PaymentKind.STARS,
        CardPayment.status == CardPaymentStatus.APPROVED,
        CardPayment.delivered_at.is_(None),
        at=CardPayment.decided_at,
    )
    texts = await waiting(Contribution, Contribution.status == ContributionStatus.PENDING, at=Contribution.created_at)
    attendance = await waiting(
        AttendanceRecord, AttendanceRecord.status == AttendanceStatus.PENDING, at=AttendanceRecord.created_at
    )
    restores = await waiting(
        User, User.status == UserStatus.LEFT, User.restore_requested_at.is_not(None), at=User.restore_requested_at
    )
    posts = await waiting(ChannelPost, ChannelPost.status == ChannelPostStatus.PENDING, at=ChannelPost.scheduled_at)
    failed_posts = int(
        await session.scalar(
            select(func.count()).where(
                ChannelPost.status == ChannelPostStatus.FAILED, ChannelPost.scheduled_at >= week_ago
            )
        )
        or 0
    )
    queues = [
        {
            "code": "support",
            "title": "📨 Javob kutayotgan murojaatlar",
            "count": tickets[0],
            "oldest_minutes": tickets[1],
            "route": "support",
        },
        {
            "code": "receipts",
            "title": "🧾 Tekshirilmagan cheklar",
            "count": receipts[0],
            "oldest_minutes": receipts[1],
            "route": "premium",
        },
        {
            "code": "stars",
            "title": "⭐ Yuborilmagan Stars",
            "count": stars[0],
            "oldest_minutes": stars[1],
            "route": "stars",
        },
        {
            "code": "community",
            "title": "💬 Ko'rib chiqilmagan fikrlar",
            "count": texts[0],
            "oldest_minutes": texts[1],
            "route": "community",
        },
        {
            "code": "attendance",
            "title": "🙋 Qo'lda davomat so'rovlari",
            "count": attendance[0],
            "oldest_minutes": attendance[1],
            "route": "events",
        },
        {
            "code": "restore",
            "title": "♻️ A'zolikni tiklash so'rovlari",
            "count": restores[0],
            "oldest_minutes": restores[1],
            "route": "members",
        },
        {
            "code": "channel",
            "title": "📣 Kanalga chiqishi kutilayotgan postlar",
            "count": posts[0],
            "oldest_minutes": None,
            "route": "channel",
        },
    ]

    rows = (
        await session.execute(
            select(AuditLog, User.first_name, User.last_name)
            .outerjoin(User, User.id == AuditLog.actor_user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(25)
        )
    ).all()
    recent = [
        {
            "at": log.created_at,
            "who": f"{first} {last or ''}".strip() if first else "Tizim",
            "action": log.action,
            "what": ACTIONS.get(log.action, log.action.replace("_", " ").lower()),
            "entity": log.entity_type,
        }
        for log, first, last in rows
    ]

    answers = (
        await session.execute(
            select(User.first_name, User.last_name, func.count())
            .join(SupportMessage, SupportMessage.admin_id == User.id)
            .where(SupportMessage.from_admin.is_(True), SupportMessage.created_at >= week_ago)
            .group_by(User.id, User.first_name, User.last_name)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    return {
        "queues": queues,
        "waiting_total": sum(item["count"] for item in queues),
        "failed_posts_week": failed_posts,
        "notifications": await queue_summary(session),
        "recent": recent,
        "answers_week": [
            {"who": f"{first} {last or ''}".strip(), "count": int(count)} for first, last, count in answers
        ],
    }
