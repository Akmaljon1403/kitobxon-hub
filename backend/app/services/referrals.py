"""«Do'stingizni taklif qiling»: every member has a personal link to the bot.

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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import User
from app.models.enums import NotificationType, PremiumSource, ScoreCategory, UserStatus
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


def link(user: User) -> str | None:
    username = get_settings().bot_username
    return f"https://t.me/{username}?start={PREFIX}{user.member_number}" if username else None


async def _on(session: AsyncSession, user: User) -> bool:
    from app.services import features

    return await features.allowed(session, user, "referrals") == "on"


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
    if referrer is None or referrer.id == user.id or not await _on(session, referrer):
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
        payload={"buttons": [{"text": "👥 Takliflarim", "app_route": "profile"}]},
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
            return await _reward(session, user_id)
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
    if (
        referrer is None
        or referrer.status != UserStatus.ACTIVE
        or referrer.deleted_at is not None
        or not await _on(session, referrer)
    ):
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
        payload=celebrate({"buttons": [{"text": "👥 Takliflarim", "app_route": "profile"}]}),
        priority=3,
    )
    return True


async def summary(session: AsyncSession, user: User) -> dict[str, Any]:
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
        "enabled": await _on(session, user),
        "link": link(user),
        "invited": invited,
        "rewarded": rewarded,
        **values,
    }
