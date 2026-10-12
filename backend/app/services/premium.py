"""Premium membership and donations, paid with Telegram Stars (XTR).

Why Stars: Telegram requires digital goods in bots to be sold for Stars, and Stars need no
payment provider, card details or contract — the club owner withdraws the collected Stars
through Fragment. Core club features stay free; Premium adds extras (see ``features``).

Flow: the member picks a plan → the bot (or the Mini App) shows Telegram's invoice → Telegram
asks us to confirm (pre-checkout: plan still on sale, price unchanged, payer is the member) →
after payment Telegram sends ``successful_payment`` → we store the payment (its Telegram charge
id is unique, so a repeated update changes nothing) and extend the membership.
Periods follow each other: buying again while premium adds the days after the current end.
"""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from aiogram.types import LabeledPrice
from sqlalchemy import Select, Uuid, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError, BadRequestError, ConflictError, NotFoundError
from app.models import Payment, PremiumDiscount, PremiumPlan, PremiumSubscription, Role, User, UserRole
from app.models.enums import (
    FeatureMode,
    NotificationType,
    PaymentKind,
    PaymentStatus,
    PremiumSource,
    SystemRole,
    UserStatus,
)
from app.services import card_payments
from app.services.audit import record_audit
from app.services.notifications import active_members, enqueue_notification, render
from app.services.settings import get_setting
from app.utils.timezone import format_date, local_tz

logger = logging.getLogger(__name__)

CURRENCY = "XTR"
# What every premium member gets in addition to the features the super admin made premium-only.
PERKS: tuple[dict[str, str], ...] = (
    {
        "icon": "🎨",
        "title": "Pasport dizaynlari",
        "description": "oltin, kumush, tungi ko'k, yoqut, okean va lavanda — 6 ta maxsus dizayn",
    },
    {"icon": "💎", "title": "Premium belgisi", "description": "reytingda ismingiz yonida va pasportingizda"},
    {"icon": "🎁", "title": "Sovg'a o'yinlarida 2 barobar imkoniyat", "description": "tasodifiy promokod o'yinlarida"},
    {
        "icon": "❤️",
        "title": "Klub rivojiga hissa",
        "description": "tushum kitoblar, tadbirlar va sovg'alarga sarflanadi",
    },
)
DONATION_AMOUNTS = (50, 100, 250, 500)
MAX_DONATION = 10_000
_PAYLOAD = re.compile(r"^(premium|donation):([0-9a-f]{32}|\d{1,6}):([0-9a-f]{32}):[0-9a-f]{8}(?::([0-9a-f]{32}))?$")
MAX_DISCOUNT = 90  # a bigger gift is Premium days, not a discount


@dataclass(frozen=True)
class InvoicePayload:
    kind: PaymentKind
    user_id: uuid.UUID
    plan_id: uuid.UUID | None = None
    amount: int | None = None
    discount_id: uuid.UUID | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def premium_payload(plan: PremiumPlan, user: User, discount: PremiumDiscount | None = None) -> str:
    suffix = f":{discount.id.hex}" if discount is not None else ""
    return f"premium:{plan.id.hex}:{user.id.hex}:{secrets.token_hex(4)}{suffix}"


def donation_payload(amount: int, user: User) -> str:
    return f"donation:{amount}:{user.id.hex}:{secrets.token_hex(4)}"


def parse_payload(payload: str) -> InvoicePayload | None:
    match = _PAYLOAD.match(payload or "")
    if not match:
        return None
    kind, target, user_hex, discount_hex = match.groups()
    if kind == "premium":
        if len(target) != 32:
            return None
        return InvoicePayload(
            PaymentKind.PREMIUM,
            uuid.UUID(hex=user_hex),
            plan_id=uuid.UUID(hex=target),
            discount_id=uuid.UUID(hex=discount_hex) if discount_hex else None,
        )
    if len(target) == 32 or discount_hex:
        return None
    return InvoicePayload(PaymentKind.DONATION, uuid.UUID(hex=user_hex), amount=int(target))


# ---------------------------------------------------------------------------- membership


def _active_condition(now: datetime) -> Any:
    return (
        PremiumSubscription.revoked_at.is_(None),
        PremiumSubscription.starts_at <= now,
        PremiumSubscription.ends_at > now,
    )


# A gift "for life" ends on this date; super administrators are premium for life by their role.
LIFETIME_UNTIL = datetime(2099, 12, 31, tzinfo=UTC)


def lifetime_holders() -> Select[tuple[uuid.UUID]]:
    """Super administrators run the club, so every Premium feature is always theirs."""
    return select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.code == SystemRole.SUPER_ADMIN)


def _subscribers(now: datetime) -> Select[tuple[uuid.UUID]]:
    return select(PremiumSubscription.user_id).where(*_active_condition(now))


def premium_condition(user_id_column: Any, now: datetime | None = None) -> Any:
    """SQL condition: the user is premium now (a current period or a super administrator)."""
    moment = now or _now()
    return or_(user_id_column.in_(_subscribers(moment)), user_id_column.in_(lifetime_holders()))


async def is_premium(session: AsyncSession, user_id: uuid.UUID) -> bool:
    return bool(await session.scalar(select(premium_condition(literal(user_id, Uuid)))))


async def is_lifetime(session: AsyncSession, user_id: uuid.UUID) -> bool:
    if await session.scalar(select(lifetime_holders().where(UserRole.user_id == user_id).exists())):
        return True
    return bool(
        await session.scalar(
            select(
                exists().where(
                    PremiumSubscription.user_id == user_id,
                    PremiumSubscription.revoked_at.is_(None),
                    PremiumSubscription.ends_at >= LIFETIME_UNTIL - timedelta(days=1),
                )
            )
        )
    )


async def premium_among(session: AsyncSession, user_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not user_ids:
        return set()
    return set(await session.scalars(select(User.id).where(User.id.in_(user_ids), premium_condition(User.id))))


async def premium_until(session: AsyncSession, user_id: uuid.UUID) -> datetime | None:
    """End of the member's paid-up time (including periods that start later)."""
    return await session.scalar(
        select(func.max(PremiumSubscription.ends_at)).where(
            PremiumSubscription.user_id == user_id,
            PremiumSubscription.revoked_at.is_(None),
            PremiumSubscription.ends_at > _now(),
        )
    )


def premium_members() -> Select[tuple[uuid.UUID]]:
    """Active members who are premium right now (for messages)."""
    return active_members().where(premium_condition(User.id))


def non_premium_members() -> Select[tuple[uuid.UUID]]:
    return active_members().where(~premium_condition(User.id))


async def _extend(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    days: int,
    source: PremiumSource,
    plan_id: uuid.UUID | None = None,
    payment_id: uuid.UUID | None = None,
    granted_by: uuid.UUID | None = None,
    note: str | None = None,
) -> PremiumSubscription:
    now = _now()
    start = max(now, await premium_until(session, user_id) or now)
    subscription = PremiumSubscription(
        user_id=user_id,
        source=source,
        plan_id=plan_id,
        payment_id=payment_id,
        starts_at=start,
        ends_at=start + timedelta(days=days),
        granted_by=granted_by,
        note=note,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def _tell(
    session: AsyncSession, user_id: uuid.UUID, message: str, dedup_key: str, *, festive: bool = False
) -> None:
    text = await render(session, NotificationType.PREMIUM, message=message)
    if text is not None:
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.PREMIUM,
            text=text,
            dedup_key=dedup_key,
            payload={
                "buttons": [{"text": "💎 Premium", "app_route": "premium"}],
                **({"mood": "CELEBRATE"} if festive else {}),
            },
            priority=2,
        )


async def grant(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    days: int | None,
    note: str | None,
    lifetime: bool = False,
) -> PremiumSubscription:
    """Premium given by an administrator (a prize, paid in cash, a gift) — for N days or for life."""
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "A'zo topilmadi.")
    if lifetime:
        subscription = PremiumSubscription(
            user_id=user_id,
            source=PremiumSource.MANUAL,
            starts_at=_now(),
            ends_at=LIFETIME_UNTIL,
            granted_by=actor_id,
            note=note,
        )
        session.add(subscription)
        await session.flush()
        message = "Sizga umrbod Premium a'zolik sovg'a qilindi! ♾ Barcha Premium imkoniyatlari endi doim siz bilan."
    else:
        if not days:
            raise BadRequestError("DAYS_REQUIRED", "Kunlar sonini kiriting yoki «Umrbod»ni tanlang.")
        subscription = await _extend(
            session, user_id=user_id, days=days, source=PremiumSource.MANUAL, granted_by=actor_id, note=note
        )
        until = format_date(subscription.ends_at)
        message = f"Sizga {days} kunlik Premium a'zolik sovg'a qilindi! Amal qiladi: {until} gacha."
    record_audit(
        session,
        actor_id=actor_id,
        action="PREMIUM_GRANT",
        entity_type="premium_subscription",
        entity_id=subscription.id,
        after={"user_id": str(user_id), "days": days, "lifetime": lifetime, "note": note},
    )
    await _tell(session, user_id, message, f"premium:grant:{subscription.id}", festive=True)
    await session.commit()
    return subscription


MAX_BULK_DAYS = 366


def gift_audience(
    *,
    faculty_id: uuid.UUID | None = None,
    course: int | None = None,
    group_name: str | None = None,
    only_without_premium: bool = False,
) -> Select[tuple[uuid.UUID]]:
    """Who a mass gift reaches: active registered members of a faculty / course / group (or everybody),
    never the super administrators (theirs is for life) nor anyone who already has Premium for life."""
    from app.services.members import normalize_group

    now = _now()
    query = active_members().where(User.registered_at.is_not(None), User.id.not_in(lifetime_holders()))
    query = query.where(
        ~exists().where(
            PremiumSubscription.user_id == User.id,
            PremiumSubscription.revoked_at.is_(None),
            PremiumSubscription.ends_at >= LIFETIME_UNTIL - timedelta(days=1),
        )
    )
    if faculty_id is not None:
        query = query.where(User.faculty_id == faculty_id)
    if course is not None:
        query = query.where(User.course == course, User.graduated_at.is_(None))
    if group_name:
        query = query.where(User.group_name == normalize_group(group_name))
    if only_without_premium:
        query = query.where(~premium_condition(User.id, now))
    return query


async def grant_many(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    days: int,
    note: str | None,
    faculty_id: uuid.UUID | None = None,
    course: int | None = None,
    group_name: str | None = None,
    only_without_premium: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Premium for N days to many at once — everybody, or a faculty, a course, a group. Members who have
    Premium get the days added after their current period. Each is told; the payments chat gets one line."""
    if not 1 <= days <= MAX_BULK_DAYS:
        raise BadRequestError("DAYS_RANGE", f"Kunlar soni 1 dan {MAX_BULK_DAYS} gacha bo'lsin.")
    audience = gift_audience(
        faculty_id=faculty_id, course=course, group_name=group_name, only_without_premium=only_without_premium
    )
    user_ids = list(await session.scalars(audience))
    if dry_run:
        return {"recipients": len(user_ids)}
    if not user_ids:
        raise ConflictError("NOBODY", "Tanlangan shartga mos a'zo topilmadi.")
    batch = uuid.uuid4()
    reason = (note or "").strip()[:200]
    stored_note = f"Ommaviy sovg'a{': ' + reason if reason else ''} [{batch.hex[:8]}]"
    for user_id in user_ids:
        subscription = await _extend(
            session, user_id=user_id, days=days, source=PremiumSource.MANUAL, granted_by=actor_id, note=stored_note
        )
        why = f" ({reason})" if reason else ""
        await _tell(
            session,
            user_id,
            f"🎁 Klub sizga {days} kunlik Premium a'zolikni sovg'a qildi{why}! Amal qiladi: "
            f"{format_date(subscription.ends_at)} gacha. Barcha 💎 imkoniyatlardan bemalol foydalaning!",
            f"premium:gift:{batch}:{user_id}",
            festive=True,
        )
    target = await _gift_target_text(session, faculty_id, course, group_name, only_without_premium)
    record_audit(
        session,
        actor_id=actor_id,
        action="PREMIUM_GRANT_BULK",
        entity_type="premium_subscription",
        entity_id=str(batch),
        after={
            "recipients": len(user_ids),
            "days": days,
            "note": reason or None,
            "target": target,
        },
    )
    await session.commit()
    from app.services import payments_chat

    actor = await session.get(User, actor_id)
    who = f"{actor.first_name} {actor.last_name}" if actor else "—"
    await payments_chat.post(
        session,
        f"🎁 <b>Ommaviy Premium sovg'a</b>: {len(user_ids)} nafar a'zoga {days} kun\n"
        f"Kimga: {payments_chat._e(target)}"
        + (f"\nSabab: {payments_chat._e(reason)}" if reason else "")
        + f"\nBerdi: {payments_chat._e(who)}",
    )
    return {"recipients": len(user_ids), "batch": batch.hex[:8]}


async def _gift_target_text(
    session: AsyncSession,
    faculty_id: uuid.UUID | None,
    course: int | None,
    group_name: str | None,
    only_without_premium: bool,
) -> str:
    from app.models import Faculty

    parts = []
    if faculty_id is not None:
        faculty = await session.get(Faculty, faculty_id)
        parts.append(faculty.name if faculty else "fakultet")
    if course is not None:
        parts.append(f"{course}-kurs")
    if group_name:
        parts.append(f"{group_name} guruh")
    text = ", ".join(parts) if parts else "barcha a'zolar"
    return text + (" (faqat Premium'i yo'qlar)" if only_without_premium else "")


# ---------------------------------------------------------------------------- trial, discounts


async def trial_days(session: AsyncSession, user: User) -> int:
    """Days of the free trial the member can still start (0: not offered or already used)."""
    from app.services import features

    days = int(await get_setting(session, "premium.trial_days"))
    if days <= 0 or await features.mode(session, "premium") == FeatureMode.OFF:
        return 0
    if await is_lifetime(session, user.id):
        return 0
    had = await session.scalar(select(exists().where(PremiumSubscription.user_id == user.id)))
    return 0 if had else days


async def cancel_period(session: AsyncSession, subscription_id: uuid.UUID) -> None:
    """Take back one Premium period (a card payment confirmed by mistake); later periods move up.
    The caller commits."""
    period = await session.get(PremiumSubscription, subscription_id)
    if period is None or period.revoked_at is not None:
        return
    now = _now()
    period.revoked_at = now
    unused = period.ends_at - max(period.starts_at, now)
    if unused <= timedelta(0):
        return
    later = await session.scalars(
        select(PremiumSubscription).where(
            PremiumSubscription.user_id == period.user_id,
            PremiumSubscription.id != period.id,
            PremiumSubscription.revoked_at.is_(None),
            PremiumSubscription.starts_at >= period.ends_at - timedelta(seconds=1),
        )
    )
    for item in later:
        item.starts_at -= unused
        item.ends_at -= unused


async def on_trial(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """Premium right now only thanks to the free trial (the app marks Premium features for them)."""
    now = _now()
    sources = set(
        await session.scalars(
            select(PremiumSubscription.source).where(
                PremiumSubscription.user_id == user_id,
                PremiumSubscription.revoked_at.is_(None),
                PremiumSubscription.starts_at <= now,
                PremiumSubscription.ends_at > now,
            )
        )
    )
    return sources == {PremiumSource.TRIAL} and not await is_lifetime(session, user_id)


async def welcome_trial(session: AsyncSession, user: User) -> PremiumSubscription | None:
    """The free trial switches on by itself when a member joins (the welcome message tells about it).
    Never breaks the registration: returns None when there is no trial to give."""
    try:
        await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"trial:{user.id}"))))
        days = await trial_days(session, user)
        if not days:
            await session.commit()  # releases the lock; nothing was changed
            return None
        subscription = await _extend(session, user_id=user.id, days=days, source=PremiumSource.TRIAL, note="sinov")
        record_audit(
            session,
            actor_id=None,
            action="PREMIUM_TRIAL",
            entity_type="premium_subscription",
            entity_id=subscription.id,
            after={"days": days, "automatic": True},
        )
        await session.commit()
        return subscription
    except Exception:
        await session.rollback()
        logger.exception("The welcome trial could not be started")
        return None


async def start_trial(session: AsyncSession, user: User) -> PremiumSubscription:
    """The member's one free trial: every Premium feature for a few days, no payment."""
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"trial:{user.id}"))))
    days = await trial_days(session, user)
    if not days:
        raise ConflictError("TRIAL_UNAVAILABLE", "Bepul sinov muddatidan allaqachon foydalangansiz.")
    subscription = await _extend(session, user_id=user.id, days=days, source=PremiumSource.TRIAL, note="sinov")
    record_audit(
        session,
        actor_id=user.id,
        action="PREMIUM_TRIAL",
        entity_type="premium_subscription",
        entity_id=subscription.id,
        after={"days": days},
    )
    await _tell(
        session,
        user.id,
        f"🎁 {days} kunlik bepul Premium boshlandi! Oltin pasport, to'liq reyting, sertifikat PDF va boshqa "
        f"imkoniyatlarni sinab ko'ring. Sinov {format_date(subscription.ends_at)} gacha — pul yechilmaydi.",
        f"premium:trial:{user.id}",
        festive=True,
    )
    await session.commit()
    return subscription


def _usable(discount: PremiumDiscount | None, user_id: uuid.UUID) -> bool:
    return (
        discount is not None
        and discount.user_id == user_id
        and discount.used_at is None
        and discount.valid_until > _now()
    )


async def active_discount(session: AsyncSession, user_id: uuid.UUID) -> PremiumDiscount | None:
    """The member's best unused, unexpired personal discount."""
    return await session.scalar(
        select(PremiumDiscount)
        .where(
            PremiumDiscount.user_id == user_id,
            PremiumDiscount.used_at.is_(None),
            PremiumDiscount.valid_until > _now(),
        )
        .order_by(PremiumDiscount.percent.desc(), PremiumDiscount.valid_until)
        .limit(1)
    )


async def give_discount(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    percent: int,
    days: int,
    note: str,
    giveaway_id: uuid.UUID | None = None,
) -> PremiumDiscount:
    """A personal Premium discount (the caller commits); the member is told."""
    if not 1 <= percent <= MAX_DISCOUNT:
        raise BadRequestError("DISCOUNT_RANGE", f"Chegirma 1% dan {MAX_DISCOUNT}% gacha bo'lishi mumkin.")
    discount = PremiumDiscount(
        user_id=user_id,
        percent=percent,
        valid_until=_now() + timedelta(days=days),
        note=note[:255],
        giveaway_id=giveaway_id,
    )
    session.add(discount)
    await session.flush()
    return discount


async def remind_expiring(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: one friendly message the day before a Premium period (or the trial) ends,
    unless the member already has the next period. Only in the daytime."""
    now = now or _now()
    local = now.astimezone(local_tz())
    if not 10 <= local.hour < 20:
        return 0
    later = aliased(PremiumSubscription)
    ending = list(
        await session.scalars(
            select(PremiumSubscription).where(
                PremiumSubscription.revoked_at.is_(None),
                PremiumSubscription.ends_at > now,
                PremiumSubscription.ends_at <= now + timedelta(hours=26),
                ~exists().where(
                    later.user_id == PremiumSubscription.user_id,
                    later.revoked_at.is_(None),
                    later.ends_at > PremiumSubscription.ends_at,
                ),
                PremiumSubscription.user_id.not_in(lifetime_holders()),
            )
        )
    )
    for subscription in ending:
        if subscription.source == PremiumSource.TRIAL:
            message = (
                "🎁 Bepul Premium sinovingiz ertaga tugaydi. Yoqdimi? Davom ettirish arzon — oyiga bir piyola choy "
                "narxida. Tanlash: 💎 Premium bo'limi."
            )
        else:
            message = (
                f"Premium muddatingiz {format_date(subscription.ends_at)} da tugaydi. Davom ettirmoqchi bo'lsangiz — "
                "💎 Premium bo'limidan uzaytirishingiz mumkin. Klubni qo'llab-quvvatlaganingiz uchun rahmat!"
            )
        await _tell(session, subscription.user_id, message, f"premium:ending:{subscription.id}")
    return len(ending)


async def revoke_subscription(
    session: AsyncSession, *, actor_id: uuid.UUID, subscription_id: uuid.UUID, reason: str
) -> PremiumSubscription:
    subscription = await session.get(PremiumSubscription, subscription_id)
    if subscription is None:
        raise NotFoundError("SUBSCRIPTION_NOT_FOUND", "Obuna topilmadi.")
    if subscription.revoked_at is not None:
        raise ConflictError("SUBSCRIPTION_REVOKED", "Obuna allaqachon bekor qilingan.")
    subscription.revoked_at = _now()
    record_audit(
        session,
        actor_id=actor_id,
        action="PREMIUM_REVOKE",
        entity_type="premium_subscription",
        entity_id=subscription.id,
        reason=reason,
    )
    await session.commit()
    return subscription


# ---------------------------------------------------------------------------- plans


async def list_plans(session: AsyncSession, *, active_only: bool = True) -> list[PremiumPlan]:
    query = select(PremiumPlan).order_by(PremiumPlan.sort_order, PremiumPlan.stars)
    if active_only:
        query = query.where(PremiumPlan.is_active.is_(True))
    return list(await session.scalars(query))


async def get_plan(session: AsyncSession, plan_id: uuid.UUID, *, active: bool = True) -> PremiumPlan:
    plan = await session.get(PremiumPlan, plan_id)
    if plan is None or (active and not plan.is_active):
        raise NotFoundError("PLAN_NOT_FOUND", "Bu tarif hozir sotuvda yo'q.")
    return plan


async def update_plan(
    session: AsyncSession, *, actor_id: uuid.UUID, plan_id: uuid.UUID, changes: dict[str, Any]
) -> PremiumPlan:
    plan = await get_plan(session, plan_id, active=False)
    before = {field: getattr(plan, field) for field in changes}
    for field, value in changes.items():
        setattr(plan, field, value)
    record_audit(
        session,
        actor_id=actor_id,
        action="PREMIUM_PLAN_UPDATE",
        entity_type="premium_plan",
        entity_id=plan.id,
        before=before,
        after=changes,
    )
    await session.commit()
    return plan


# ---------------------------------------------------------------------------- invoices and payments


def discounted(price: int, percent: int | None) -> int:
    """The price after a personal discount (never below 1)."""
    if not percent:
        return price
    return max(1, round(price * (100 - percent) / 100))


def plan_invoice(plan: PremiumPlan, user: User, discount: PremiumDiscount | None = None) -> dict[str, Any]:
    """Arguments for Telegram's sendInvoice / createInvoiceLink."""
    stars = discounted(plan.stars, discount.percent if discount else None)
    label = f"Premium {plan.title}" + (f" (−{discount.percent}%)" if discount else "")
    return {
        "title": f"Kitobxon Premium — {plan.title}",
        "description": plan.description or f"{plan.days} kunlik Premium a'zolik",
        "payload": premium_payload(plan, user, discount),
        "currency": CURRENCY,
        "prices": [LabeledPrice(label=label, amount=stars)],
    }


def donation_invoice(amount: int, user: User) -> dict[str, Any]:
    if not 1 <= amount <= MAX_DONATION:
        raise BadRequestError("INVALID_AMOUNT", "Noto'g'ri miqdor.")
    return {
        "title": "Klubni qo'llab-quvvatlash",
        "description": "Kitobxonlar klubi rivojiga hissa — rahmat! ❤️",
        "payload": donation_payload(amount, user),
        "currency": CURRENCY,
        "prices": [LabeledPrice(label="Hissa", amount=amount)],
    }


async def invoice_link(
    session: AsyncSession, bot: Bot, user: User, *, plan_id: uuid.UUID | None, amount: int | None
) -> str:
    """A t.me/$... link the Mini App opens with ``Telegram.WebApp.openInvoice``."""
    if plan_id is not None:
        await _ensure_on_sale(session, "premium")
        arguments = plan_invoice(await get_plan(session, plan_id), user, await active_discount(session, user.id))
    elif amount is not None:
        await _ensure_on_sale(session, "donations")
        arguments = donation_invoice(amount, user)
    else:
        raise BadRequestError("NOTHING_TO_PAY", "Tarif yoki miqdorni tanlang.")
    return await bot.create_invoice_link(**arguments)


async def _ensure_on_sale(session: AsyncSession, code: str) -> None:
    from app.services import features

    if await features.mode(session, code) == FeatureMode.OFF:
        raise features.FeatureOffError(features.get_feature(code))


async def check_pre_checkout(
    session: AsyncSession, *, telegram_user_id: int, payload: str, currency: str, total_amount: int
) -> str | None:
    """Telegram asks before taking the Stars. Returns an error for the member, or None to accept."""
    parsed = parse_payload(payload)
    if parsed is None or currency != CURRENCY:
        return "To'lov ma'lumotlari noto'g'ri. Qaytadan urinib ko'ring."
    user = await session.get(User, parsed.user_id)
    if user is None or user.telegram_id != telegram_user_id or user.status != UserStatus.ACTIVE:
        return "Bu to'lov boshqa a'zo uchun tayyorlangan."
    try:
        if parsed.kind == PaymentKind.PREMIUM:
            await _ensure_on_sale(session, "premium")
            assert parsed.plan_id is not None
            plan = await get_plan(session, parsed.plan_id)
            percent = None
            if parsed.discount_id is not None:
                discount = await session.get(PremiumDiscount, parsed.discount_id)
                if not _usable(discount, user.id):
                    return "Chegirma muddati tugagan yoki ishlatilgan. Iltimos, qaytadan tanlang."
                percent = discount.percent  # type: ignore[union-attr]
            if discounted(plan.stars, percent) != total_amount:
                return "Tarif narxi o'zgargan. Iltimos, qaytadan tanlang."
        else:
            await _ensure_on_sale(session, "donations")
            if parsed.amount != total_amount or not 1 <= total_amount <= MAX_DONATION:
                return "Miqdor noto'g'ri."
    except AppError as exc:  # not on sale any more, plan withdrawn, ...
        return exc.message
    return None


async def record_payment(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    payload: str,
    currency: str,
    total_amount: int,
    charge_id: str,
) -> tuple[Payment, PremiumSubscription | None, bool]:
    """Store a successful payment and give what was bought. Returns (payment, period, is_new)."""
    existing = await session.scalar(select(Payment).where(Payment.telegram_charge_id == charge_id))
    if existing is not None:
        subscription = await session.scalar(
            select(PremiumSubscription).where(PremiumSubscription.payment_id == existing.id)
        )
        return existing, subscription, False
    parsed = parse_payload(payload)
    user = await session.scalar(select(User).where(User.telegram_id == telegram_user_id))
    if parsed is None or user is None or currency != CURRENCY:
        # Cannot happen after our pre-checkout; the caller logs the charge id so an admin can refund it.
        raise BadRequestError("UNKNOWN_PAYMENT", f"Unrecognised payment {charge_id}")
    plan = await session.get(PremiumPlan, parsed.plan_id) if parsed.plan_id else None
    payment = Payment(
        user_id=user.id,
        kind=parsed.kind,
        amount=total_amount,
        currency=currency,
        plan_id=plan.id if plan else None,
        invoice_payload=payload,
        telegram_charge_id=charge_id,
    )
    session.add(payment)
    await session.flush()
    subscription = None
    if parsed.discount_id is not None:
        discount = await session.get(PremiumDiscount, parsed.discount_id)
        if discount is not None and discount.used_at is None:
            discount.used_at = _now()
            discount.used_for = f"payment:{payment.id}"
    if parsed.kind == PaymentKind.PREMIUM:
        subscription = await _extend(
            session,
            user_id=user.id,
            days=plan.days if plan else 30,
            source=PremiumSource.STARS,
            plan_id=plan.id if plan else None,
            payment_id=payment.id,
        )
    record_audit(
        session,
        actor_id=user.id,
        action="PAYMENT",
        entity_type="payment",
        entity_id=payment.id,
        after={"kind": str(parsed.kind), "amount": total_amount, "plan": plan.code if plan else None},
    )
    await session.commit()
    return payment, subscription, True


async def refund(session: AsyncSession, bot: Bot, *, actor_id: uuid.UUID, payment_id: uuid.UUID) -> Payment:
    """Give the Stars back (Telegram) and end the premium period bought with them."""
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise NotFoundError("PAYMENT_NOT_FOUND", "To'lov topilmadi.")
    if payment.status == PaymentStatus.REFUNDED:
        raise ConflictError("PAYMENT_REFUNDED", "Bu to'lov allaqachon qaytarilgan.")
    user = await session.get(User, payment.user_id)
    assert user is not None
    await bot.refund_star_payment(user_id=user.telegram_id, telegram_payment_charge_id=payment.telegram_charge_id)
    payment.status = PaymentStatus.REFUNDED
    payment.refunded_at = _now()
    payment.refunded_by = actor_id
    for subscription in await session.scalars(
        select(PremiumSubscription).where(
            PremiumSubscription.payment_id == payment.id, PremiumSubscription.revoked_at.is_(None)
        )
    ):
        subscription.revoked_at = _now()
    record_audit(session, actor_id=actor_id, action="PAYMENT_REFUND", entity_type="payment", entity_id=payment.id)
    await _tell(
        session,
        payment.user_id,
        f"{payment.amount} ⭐ hisobingizga qaytarildi.",
        f"premium:refund:{payment.id}",
    )
    await session.commit()
    from app.services import payments_chat

    await payments_chat.stars_refund(session, payment, user, await session.get(User, actor_id))
    return payment


# ---------------------------------------------------------------------------- views


async def member_status(session: AsyncSession, user: User) -> dict[str, Any]:
    from app.services import features

    current_modes = await features.modes(session)
    premium_features = [
        {"code": feature.code, "title": feature.title, "description": feature.description}
        for feature in features.FEATURES
        if current_modes[feature.code] == FeatureMode.PREMIUM
    ]
    discount = await active_discount(session, user.id)
    percent = discount.percent if discount else None
    return {
        "is_premium": await is_premium(session, user.id),
        "lifetime": await is_lifetime(session, user.id),
        "until": await premium_until(session, user.id),
        "trial_days": await trial_days(session, user),
        "discount": (
            {"percent": discount.percent, "valid_until": discount.valid_until, "note": discount.note}
            if discount
            else None
        ),
        "store_open": current_modes["premium"] != FeatureMode.OFF,
        "donations_open": current_modes["donations"] != FeatureMode.OFF,
        "plans": [
            {
                "id": plan.id,
                "title": plan.title,
                "description": plan.description,
                "stars": plan.stars,
                "days": plan.days,
                "price_uzs": plan.price_uzs,
                "stars_now": discounted(plan.stars, percent),
                "price_uzs_now": card_payments.discounted_uzs(plan.price_uzs, percent),
            }
            for plan in await list_plans(session)
        ],
        "card": await card_payments.card_details(session),
        "stars_packages": await card_payments.stars_offer(session),
        "donation_amounts": list(DONATION_AMOUNTS),
        "premium_features": premium_features,
        "perks": [dict(perk) for perk in PERKS],
    }


async def overview(session: AsyncSession) -> dict[str, Any]:
    now = _now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def total(*conditions: Any) -> int:
        return int(
            await session.scalar(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == PaymentStatus.PAID, *conditions
                )
            )
            or 0
        )

    return {
        "premium_members": int(
            await session.scalar(select(func.count()).select_from(premium_members().subquery())) or 0
        ),
        "stars_total": await total(),
        "stars_this_month": await total(Payment.created_at >= month_start),
        "premium_stars": await total(Payment.kind == PaymentKind.PREMIUM),
        "donation_stars": await total(Payment.kind == PaymentKind.DONATION),
        "payments": int(await session.scalar(select(func.count()).select_from(Payment)) or 0),
        **await card_payments.totals(session),
    }


async def list_payments(session: AsyncSession, *, limit: int, offset: int) -> tuple[list[tuple[Payment, User]], int]:
    total = await session.scalar(select(func.count()).select_from(Payment))
    rows = await session.execute(
        select(Payment, User)
        .join(User, User.id == Payment.user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(payment, user) for payment, user in rows], int(total or 0)


async def list_subscriptions(
    session: AsyncSession, *, active_only: bool, limit: int, offset: int
) -> tuple[list[tuple[PremiumSubscription, User]], int]:
    query = select(PremiumSubscription, User).join(User, User.id == PremiumSubscription.user_id)
    if active_only:
        query = query.where(PremiumSubscription.revoked_at.is_(None), PremiumSubscription.ends_at > _now())
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.execute(query.order_by(PremiumSubscription.created_at.desc()).limit(limit).offset(offset))
    return [(subscription, user) for subscription, user in rows], int(total or 0)
