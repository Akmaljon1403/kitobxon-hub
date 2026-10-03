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

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from aiogram.types import LabeledPrice
from sqlalchemy import Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, BadRequestError, ConflictError, NotFoundError
from app.models import Payment, PremiumPlan, PremiumSubscription, User
from app.models.enums import FeatureMode, NotificationType, PaymentKind, PaymentStatus, PremiumSource, UserStatus
from app.services.audit import record_audit
from app.services.notifications import active_members, enqueue_notification, render
from app.utils.timezone import format_date

CURRENCY = "XTR"
DONATION_AMOUNTS = (50, 100, 250, 500)
MAX_DONATION = 10_000
_PAYLOAD = re.compile(r"^(premium|donation):([0-9a-f]{32}|\d{1,6}):([0-9a-f]{32}):[0-9a-f]{8}$")


@dataclass(frozen=True)
class InvoicePayload:
    kind: PaymentKind
    user_id: uuid.UUID
    plan_id: uuid.UUID | None = None
    amount: int | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def premium_payload(plan: PremiumPlan, user: User) -> str:
    return f"premium:{plan.id.hex}:{user.id.hex}:{secrets.token_hex(4)}"


def donation_payload(amount: int, user: User) -> str:
    return f"donation:{amount}:{user.id.hex}:{secrets.token_hex(4)}"


def parse_payload(payload: str) -> InvoicePayload | None:
    match = _PAYLOAD.match(payload or "")
    if not match:
        return None
    kind, target, user_hex = match.groups()
    if kind == "premium":
        if len(target) != 32:
            return None
        return InvoicePayload(PaymentKind.PREMIUM, uuid.UUID(hex=user_hex), plan_id=uuid.UUID(hex=target))
    if len(target) == 32:
        return None
    return InvoicePayload(PaymentKind.DONATION, uuid.UUID(hex=user_hex), amount=int(target))


# ---------------------------------------------------------------------------- membership


def _active_condition(now: datetime) -> Any:
    return (
        PremiumSubscription.revoked_at.is_(None),
        PremiumSubscription.starts_at <= now,
        PremiumSubscription.ends_at > now,
    )


async def is_premium(session: AsyncSession, user_id: uuid.UUID) -> bool:
    now = _now()
    return bool(
        await session.scalar(select(exists().where(PremiumSubscription.user_id == user_id, *_active_condition(now))))
    )


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
    now = _now()
    current = select(PremiumSubscription.user_id).where(*_active_condition(now))
    return active_members().where(User.id.in_(current))


def non_premium_members() -> Select[tuple[uuid.UUID]]:
    now = _now()
    current = select(PremiumSubscription.user_id).where(*_active_condition(now))
    return active_members().where(User.id.not_in(current))


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


async def _tell(session: AsyncSession, user_id: uuid.UUID, message: str, dedup_key: str) -> None:
    text = await render(session, NotificationType.PREMIUM, message=message)
    if text is not None:
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.PREMIUM,
            text=text,
            dedup_key=dedup_key,
            payload={"buttons": [{"text": "💎 Premium", "app_route": "premium"}]},
            priority=2,
        )


async def grant(
    session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, days: int, note: str | None
) -> PremiumSubscription:
    """Premium given by an administrator (a prize, paid in cash, a gift)."""
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "A'zo topilmadi.")
    subscription = await _extend(
        session, user_id=user_id, days=days, source=PremiumSource.MANUAL, granted_by=actor_id, note=note
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="PREMIUM_GRANT",
        entity_type="premium_subscription",
        entity_id=subscription.id,
        after={"user_id": str(user_id), "days": days, "note": note},
    )
    await _tell(
        session,
        user_id,
        f"Sizga {days} kunlik Premium a'zolik sovg'a qilindi! Amal qiladi: {format_date(subscription.ends_at)} gacha.",
        f"premium:grant:{subscription.id}",
    )
    await session.commit()
    return subscription


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


def plan_invoice(plan: PremiumPlan, user: User) -> dict[str, Any]:
    """Arguments for Telegram's sendInvoice / createInvoiceLink."""
    return {
        "title": f"Kitobxon Premium — {plan.title}",
        "description": plan.description or f"{plan.days} kunlik Premium a'zolik",
        "payload": premium_payload(plan, user),
        "currency": CURRENCY,
        "prices": [LabeledPrice(label=f"Premium {plan.title}", amount=plan.stars)],
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
        arguments = plan_invoice(await get_plan(session, plan_id), user)
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
            if plan.stars != total_amount:
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
    return {
        "is_premium": await is_premium(session, user.id),
        "until": await premium_until(session, user.id),
        "store_open": current_modes["premium"] != FeatureMode.OFF,
        "donations_open": current_modes["donations"] != FeatureMode.OFF,
        "plans": [
            {
                "id": plan.id,
                "title": plan.title,
                "description": plan.description,
                "stars": plan.stars,
                "days": plan.days,
            }
            for plan in await list_plans(session)
        ],
        "donation_amounts": list(DONATION_AMOUNTS),
        "premium_features": premium_features,
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
            await session.scalar(
                select(func.count(func.distinct(PremiumSubscription.user_id))).where(*_active_condition(now))
            )
            or 0
        ),
        "stars_total": await total(),
        "stars_this_month": await total(Payment.created_at >= month_start),
        "premium_stars": await total(Payment.kind == PaymentKind.PREMIUM),
        "donation_stars": await total(Payment.kind == PaymentKind.DONATION),
        "payments": int(await session.scalar(select(func.count()).select_from(Payment)) or 0),
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
