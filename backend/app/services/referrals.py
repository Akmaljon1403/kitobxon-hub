"""«🎁 Sizning foydangiz»: every member has a personal link to the bot (always open, never switched off).

A friend who registers through the link is remembered (``users.referred_by``). When the friend
comes to a club event for the first time (attendance verified by the QR code or an admin), the
member who invited them gets bonus points and a few days of Premium. Coming to an event is the
proof of a real new reader, so fake accounts earn nothing. At most ``referral.monthly_limit``
rewards a month per member.
"""

from __future__ import annotations

import html
import logging
import re
import uuid
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    AttendanceRecord,
    BookRead,
    PremiumSubscription,
    Role,
    ScoreTransaction,
    TestAttempt,
    User,
    UserRole,
)
from app.models.enums import (
    AttemptStatus,
    AttendanceStatus,
    NotificationType,
    PremiumSource,
    ReadingStatus,
    ScoreCategory,
    UserStatus,
)
from app.services.notifications import celebrate, enqueue_notification, render
from app.services.settings import get_setting
from app.utils.timezone import local_tz

logger = logging.getLogger(__name__)

PREFIX = "ref_"
_PAYLOAD = re.compile(rf"^{PREFIX}(\d{{1,9}})$")


def parse(payload: str | None) -> int | None:
    """The member number in a /start payload such as ``ref_1024``."""
    match = _PAYLOAD.match((payload or "").strip())
    return int(match.group(1)) if match else None


async def link(user: User, bot: Any = None) -> str | None:
    """The member's personal invitation link (None only while the bot's username is unknown)."""
    from app.bot.setup import resolve_bot_username

    username = await resolve_bot_username(bot)
    return f"https://t.me/{username}?start={PREFIX}{user.member_number}" if username else None


async def terms(session: AsyncSession) -> dict[str, int]:
    return {
        "points": int(await get_setting(session, "referral.points")),
        "premium_days": int(await get_setting(session, "referral.premium_days")),
        "monthly_limit": int(await get_setting(session, "referral.monthly_limit")),
    }


def reward_text(values: dict[str, Any]) -> str:
    parts = [f"+{values['points']} ball"] if values["points"] else []
    if values["premium_days"]:
        parts.append(f"{values['premium_days']} kunlik 💎 Premium")
    return " va ".join(parts) or "rahmat"


async def attach(session: AsyncSession, user: User, member_number: int | None) -> bool:
    """Remember who invited a member who has just registered. The caller commits."""
    if member_number is None or user.referred_by is not None:
        return False
    referrer = await session.scalar(
        select(User).where(
            User.member_number == member_number,
            User.status == UserStatus.ACTIVE,
            User.deleted_at.is_(None),
        )
    )
    if referrer is None or referrer.id == user.id:
        return False
    user.referred_by = referrer.id
    values = await terms(session)
    message = (
        f"👥 <b>{html.escape(user.first_name)}</b> sizning taklifingiz bilan klubga qo'shildi!\n"
        f"Birinchi tadbirda qatnashgach, sizga {reward_text(values)} beriladi. "
        "Birga o'qish — ikki karra maroqli 📚"
    )
    await enqueue_notification(
        session,
        user_id=referrer.id,
        type_=NotificationType.SYSTEM,
        text=await render(session, NotificationType.SYSTEM, message=message) or message,
        dedup_key=f"referral:joined:{user.id}",
        payload={"buttons": [{"text": "🎁 Sizning foydangiz", "app_route": "invite"}]},
        priority=4,
    )
    return True


def _month_start(now: datetime) -> datetime:
    local = now.astimezone(local_tz())
    return datetime.combine(local.date().replace(day=1), time.min, tzinfo=local_tz())


async def on_first_attendance(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """A member came to an event: if a friend invited them, the friend gets the reward (once).
    The caller commits. Never fails the check-in itself."""
    try:
        async with session.begin_nested():  # a failure here must not undo the check-in
            rewarded = await _reward(session, user_id)
            user = await session.get(User, user_id)
            if user is not None and user.referred_by is not None:
                from app.services import achievements

                await achievements.evaluate(session, user.referred_by)  # «Birinchi do'st», «Targ'ibotchi»
            return rewarded
    except Exception:
        logger.exception("Referral reward failed")
        return False


async def _reward(session: AsyncSession, user_id: uuid.UUID) -> bool:
    from app.services import premium as premium_service
    from app.services.scoring import award_points

    user = await session.get(User, user_id)
    if user is None or user.referred_by is None or user.referral_rewarded_at is not None:
        return False
    now = datetime.now(UTC)
    referrer = await session.get(User, user.referred_by)
    if referrer is None or referrer.status != UserStatus.ACTIVE or referrer.deleted_at is not None:
        user.referral_rewarded_at = now  # nobody to thank: this invitation is closed
        return False
    values = await terms(session)
    rewarded = int(
        await session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.referred_by == referrer.id,
                User.referral_rewarded_at >= _month_start(now),
                User.id != user.id,
            )
        )
        or 0
    )
    if values["monthly_limit"] and rewarded >= values["monthly_limit"]:
        return False  # this month's limit is reached: rewarded at the friend's next event
    user.referral_rewarded_at = now
    name = f"{user.first_name} {user.last_name}".strip()
    if values["points"]:
        await award_points(
            session,
            user_id=referrer.id,
            amount=values["points"],
            category=ScoreCategory.CAMPAIGN,
            idempotency_key=f"referral:{user.id}",
            source_type="REFERRAL",
            source_id=user.id,
            reason=f"Taklif qilingan do'st: {name}",
        )
    if values["premium_days"] and not await premium_service.is_lifetime(session, referrer.id):
        await premium_service._extend(
            session,
            user_id=referrer.id,
            days=values["premium_days"],
            source=PremiumSource.REFERRAL,
            note=f"Do'stni taklif qilgani uchun: {name}",
        )
    message = (
        f"🎉 <b>Do'stingiz {html.escape(user.first_name)} birinchi tadbirda qatnashdi!</b>\n\n"
        f"Taklifingiz uchun rahmat — sizga {reward_text(values)}. "
        "Yana kimni kitob olamiga olib kirasiz? 📚"
    )
    await enqueue_notification(
        session,
        user_id=referrer.id,
        type_=NotificationType.SYSTEM,
        text=await render(session, NotificationType.SYSTEM, message=message) or message,
        dedup_key=f"referral:rewarded:{user.id}",
        payload=celebrate({"buttons": [{"text": "🎁 Sizning foydangiz", "app_route": "invite"}]}),
        priority=3,
    )
    return True


async def summary(session: AsyncSession, user: User, bot: Any = None) -> dict[str, Any]:
    """The member's own invitations (for the Mini App and the bot)."""
    invited = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.referred_by == user.id, User.deleted_at.is_(None))
        )
        or 0
    )
    rewarded = int(
        await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.referred_by == user.id, User.referral_rewarded_at.is_not(None))
        )
        or 0
    )
    values = await terms(session)
    return {
        "enabled": True,  # always open
        "link": await link(user, bot),
        "invited": invited,
        "rewarded": rewarded,
        **values,
    }


# ---------------------------------------------------------------------------- «Sizning foydangiz»

SOURCES = ("REFERRAL", "REFERRAL_CONTEST")  # points a member earned for inviting friends
MAX_FRIENDS_LISTED = 100


def came_to_event(user_id: Any, before: datetime | None = None) -> Any:
    """SQL condition: the member has at least one verified club attendance (before a moment)."""
    conditions = [AttendanceRecord.user_id == user_id, AttendanceRecord.status == AttendanceStatus.VERIFIED]
    if before is not None:
        conditions.append(AttendanceRecord.checked_in_at < before)
    return exists().where(*conditions)


def not_staff(user_id: Any) -> Any:
    """SQL condition: not a club administrator (administrators never compete with members)."""
    from app.services.rbac import ADMIN_ROLES

    return ~exists().where(UserRole.user_id == user_id, UserRole.role_id == Role.id, Role.code.in_(ADMIN_ROLES))


async def impact(session: AsyncSession, user: User) -> dict[str, Any]:
    """What the readers a member brought to the club have done: «Sizning foydangiz»."""
    friends = select(User.id).where(User.referred_by == user.id, User.deleted_at.is_(None))
    totals = (
        await session.execute(
            select(
                func.count(User.id),
                func.count(User.id).filter(came_to_event(User.id)),
                func.count(User.id).filter(User.status == UserStatus.ACTIVE),
            ).where(User.referred_by == user.id, User.deleted_at.is_(None))
        )
    ).one()
    points = await session.scalar(
        select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(ScoreTransaction.user_id.in_(friends))
    )
    books = await session.scalar(
        select(func.count(BookRead.id)).where(BookRead.user_id.in_(friends), BookRead.status == ReadingStatus.COMPLETED)
    )
    visits = await session.scalar(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.user_id.in_(friends), AttendanceRecord.status == AttendanceStatus.VERIFIED
        )
    )
    tests = await session.scalar(
        select(func.count(TestAttempt.id)).where(
            TestAttempt.user_id.in_(friends), TestAttempt.status == AttemptStatus.SUBMITTED
        )
    )
    earned_points = await session.scalar(
        select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(
            ScoreTransaction.user_id == user.id, ScoreTransaction.source_type.in_(SOURCES)
        )
    )
    premium_periods = (
        await session.execute(
            select(PremiumSubscription.starts_at, PremiumSubscription.ends_at).where(
                PremiumSubscription.user_id == user.id,
                PremiumSubscription.source == PremiumSource.REFERRAL,
                PremiumSubscription.revoked_at.is_(None),
            )
        )
    ).all()
    premium_days = sum(max(0, round((ends - starts).total_seconds() / 86400)) for starts, ends in premium_periods)
    return {
        "invited": int(totals[0]),
        "came_to_events": int(totals[1]),
        "active": int(totals[2]),
        "friends_points": int(points or 0),
        "friends_books": int(books or 0),
        "friends_visits": int(visits or 0),
        "friends_tests": int(tests or 0),
        "earned_points": int(earned_points or 0),
        "earned_premium_days": premium_days,
    }


async def friends(session: AsyncSession, user: User, details: str) -> list[dict[str, Any]]:
    """The friends a member invited, newest first (what is shown depends on ``referral.friend_details``)."""
    from app.services.ranking import display_name

    if details == "COUNT":
        return []
    friend = aliased(User)
    points = (
        select(func.coalesce(func.sum(ScoreTransaction.amount), 0))
        .where(ScoreTransaction.user_id == friend.id)
        .scalar_subquery()
    )
    books = (
        select(func.count(BookRead.id))
        .where(BookRead.user_id == friend.id, BookRead.status == ReadingStatus.COMPLETED)
        .scalar_subquery()
    )
    visits = (
        select(func.count(AttendanceRecord.id))
        .where(AttendanceRecord.user_id == friend.id, AttendanceRecord.status == AttendanceStatus.VERIFIED)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(friend.first_name, friend.last_name, friend.registered_at, friend.status, points, books, visits)
        .where(friend.referred_by == user.id, friend.deleted_at.is_(None))
        .order_by(friend.registered_at.desc().nulls_last())
        .limit(MAX_FRIENDS_LISTED)
    )
    result = []
    for first_name, last_name, registered_at, status, friend_points, friend_books, friend_visits in rows:
        item: dict[str, Any] = {
            "name": display_name(first_name, last_name, "SHORT"),
            "joined_at": registered_at,
            "came_to_event": int(friend_visits or 0) > 0,
            "active": status == UserStatus.ACTIVE,
        }
        if details == "FULL":
            item.update(points=int(friend_points or 0), books=int(friend_books or 0), visits=int(friend_visits or 0))
        result.append(item)
    return result


def inviters(
    *,
    rule: str,
    joined_from: datetime | None = None,
    joined_until: datetime | None = None,
    min_friend_points: int = 0,
    counted_until: datetime | None = None,
) -> Select[Any]:
    """Members and how many friends of theirs count, best first: (user_id, friends, last_joined_at).

    ``rule``: REGISTERED (an active account), ATTENDED (came to an event) or POINTS (earned
    ``min_friend_points``); ``counted_until`` — attendance and points made before this moment."""
    friend = aliased(User)
    conditions: list[Any] = [
        friend.referred_by.is_not(None),
        friend.deleted_at.is_(None),
        friend.status == UserStatus.ACTIVE,
    ]
    if joined_from is not None:
        conditions.append(friend.registered_at >= joined_from)
    if joined_until is not None:
        conditions.append(friend.registered_at < joined_until)
    if rule == "ATTENDED":
        conditions.append(came_to_event(friend.id, counted_until))
    elif rule == "POINTS":
        earned = select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(
            ScoreTransaction.user_id == friend.id,
            *([ScoreTransaction.created_at < counted_until] if counted_until is not None else []),
        )
        conditions.append(earned.scalar_subquery() >= max(min_friend_points, 1))
    return (
        select(
            friend.referred_by.label("user_id"),
            func.count(friend.id).label("friends"),
            func.max(friend.registered_at).label("last_joined_at"),
        )
        .where(*conditions)
        .group_by(friend.referred_by)
    )


async def leaderboard(session: AsyncSession, user: User, size: int, rule: str) -> dict[str, Any]:
    """«Eng faol taklif qiluvchilar» of all time, and the member's own place."""
    from app.services.ranking import display_name

    counted = inviters(rule=rule).subquery()
    ranked = (
        select(
            func.row_number()
            .over(order_by=(counted.c.friends.desc(), counted.c.last_joined_at.asc(), User.registered_at.asc()))
            .label("place"),
            User.id,
            User.first_name,
            User.last_name,
            counted.c.friends,
        )
        .join(User, User.id == counted.c.user_id)
        .where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), not_staff(User.id))
    ).subquery()
    name_format = str(await get_setting(session, "ranking.public_name_format"))
    top = (await session.execute(select(ranked).where(ranked.c.place <= size).order_by(ranked.c.place))).all()
    mine = (await session.execute(select(ranked).where(ranked.c.id == user.id))).first()
    return {
        "rule": rule,
        "items": [
            {
                "place": int(row.place),
                "name": display_name(row.first_name, row.last_name, name_format),
                "friends": int(row.friends),
                "me": row.id == user.id,
            }
            for row in top
        ],
        "my_place": int(mine.place) if mine else None,
        "my_friends": int(mine.friends) if mine else 0,
    }


async def overview(session: AsyncSession, user: User, bot: Any = None) -> dict[str, Any]:
    """Everything for the «🎁 Sizning foydangiz» page: the link, the reward terms, the impact, the friends
    and the all-time table (each part as the settings allow)."""
    details = str(await get_setting(session, "referral.friend_details"))
    size = int(await get_setting(session, "referral.leaderboard_size"))
    rule = str(await get_setting(session, "referral.leaderboard_rule"))
    return {
        **await summary(session, user, bot),
        "impact": await impact(session, user),
        "friend_details": details,
        "friends": await friends(session, user, details),
        "leaderboard": await leaderboard(session, user, size, rule) if size else None,
    }
