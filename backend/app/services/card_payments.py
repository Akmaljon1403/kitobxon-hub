"""Premium paid to the club's bank card.

Telegram Stars are the automatic way to pay. Many students have no Stars but do have a local
card, so they can also transfer the price to the club's card and send the receipt (a screenshot).
The super admin checks the receipt and confirms it in the bot or the Admin Panel; Premium then
switches on by itself and the member is told. Nothing is charged by the bot: it only records.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import UTC, datetime
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import CardPayment, PremiumPlan, User
from app.models.enums import CardPaymentStatus, FeatureMode, NotificationType, PaymentKind, PremiumSource
from app.services.audit import record_audit
from app.services.notifications import enqueue_for_members, enqueue_notification, render
from app.services.settings import get_setting
from app.services.storage import get_storage

MAX_RECEIPT_BYTES = 10 * 1024 * 1024
MAX_PENDING = 3
MIN_DONATION_UZS = 1_000


def format_uzs(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


async def card_details(session: AsyncSession) -> dict[str, str] | None:
    """The card members pay to, or None while card payments are off or not set up."""
    from app.services import features

    if await features.mode(session, "card_payments") == FeatureMode.OFF:
        return None
    number = str(await get_setting(session, "payments.card_number")).strip()
    if not number:
        return None
    return {"number": number, "holder": str(await get_setting(session, "payments.card_holder")).strip()}


def prepare_receipt(data: bytes) -> bytes:
    """Check the screenshot and keep a smaller copy without metadata."""
    if not data or len(data) > MAX_RECEIPT_BYTES:
        raise BadRequestError("RECEIPT_TOO_LARGE", "Chek rasmi 10 MB dan oshmasin.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 40_000_000:
            raise BadRequestError("RECEIPT_TOO_LARGE", "Rasm o'lchami juda katta.")
        image.verify()
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise BadRequestError("RECEIPT_INVALID", "Chek rasm (skrinshot) ko'rinishida bo'lsin.") from exc
    image.thumbnail((1600, 1600))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue()


async def submit(
    session: AsyncSession,
    user: User,
    *,
    receipt: bytes,
    plan_id: uuid.UUID | None = None,
    amount_uzs: int | None = None,
) -> CardPayment:
    """The member says "I paid": a plan (its card price) or a donation of ``amount_uzs``."""
    if await card_details(session) is None:
        raise ConflictError("CARD_PAYMENTS_OFF", "Karta orqali to'lov hozircha yoqilmagan.")
    pending = await session.scalar(
        select(func.count())
        .select_from(CardPayment)
        .where(CardPayment.user_id == user.id, CardPayment.status == CardPaymentStatus.PENDING)
    )
    if (pending or 0) >= MAX_PENDING:
        raise ConflictError("TOO_MANY_PENDING", "Avvalgi cheklaringiz hali tekshirilmoqda. Biroz kuting.")
    plan = None
    if plan_id is not None:
        plan = await session.get(PremiumPlan, plan_id)
        if plan is None or not plan.is_active or not plan.price_uzs:
            raise NotFoundError("PLAN_NOT_FOUND", "Bu tarif karta orqali sotilmaydi.")
        kind, amount = PaymentKind.PREMIUM, plan.price_uzs
    else:
        if amount_uzs is None or amount_uzs < MIN_DONATION_UZS:
            raise BadRequestError("INVALID_AMOUNT", f"Hissa kamida {format_uzs(MIN_DONATION_UZS)} bo'lsin.")
        kind, amount = PaymentKind.DONATION, amount_uzs
    prepared = await asyncio.to_thread(prepare_receipt, receipt)
    key = f"card-receipts/{user.id}/{uuid.uuid4().hex}.jpg"
    await get_storage().put(key, prepared, "image/jpeg")
    payment = CardPayment(
        user_id=user.id, kind=kind, plan_id=plan.id if plan else None, amount_uzs=amount, receipt_key=key
    )
    session.add(payment)
    await session.flush()
    record_audit(
        session,
        actor_id=user.id,
        action="CARD_PAYMENT_SUBMIT",
        entity_type="card_payment",
        entity_id=payment.id,
        after={"kind": str(kind), "amount_uzs": amount},
    )
    await _tell_admins(session, payment, user, plan)
    await session.commit()
    return payment


async def _tell_admins(session: AsyncSession, payment: CardPayment, user: User, plan: PremiumPlan | None) -> None:
    from app.services.rbac import super_admins

    what = f"💎 Premium «{plan.title}»" if plan else "❤️ Hissa"
    text = (
        f"💳 <b>Yangi karta to'lovi</b>\n\n{what} — <b>{format_uzs(payment.amount_uzs)}</b>\n"
        f"A'zo: {user.last_name} {user.first_name}"
        + (f" (@{user.telegram_username})" if user.telegram_username else "")
        + "\n\nChekni ko'rib, tasdiqlang yoki rad eting."
    )
    await enqueue_for_members(
        session,
        type_=NotificationType.PREMIUM,
        text=text,
        dedup_prefix=f"card-payment:{payment.id}",
        members=super_admins(),
        payload={
            "buttons": [
                {"text": "🧾 Chekni ko'rish", "callback": f"cp:view:{payment.id.hex}"},
                {
                    "row": [
                        {"text": "✅ Tasdiqlash", "callback": f"cp:ok:{payment.id.hex}"},
                        {"text": "❌ Rad etish", "callback": f"cp:no:{payment.id.hex}"},
                    ]
                },
            ]
        },
        priority=2,
    )


async def get(session: AsyncSession, payment_id: uuid.UUID) -> CardPayment:
    payment = await session.get(CardPayment, payment_id)
    if payment is None:
        raise NotFoundError("CARD_PAYMENT_NOT_FOUND", "To'lov topilmadi.")
    return payment


async def _member_message(session: AsyncSession, user_id: uuid.UUID, message: str, key: str) -> None:
    text = await render(session, NotificationType.PREMIUM, message=message)
    if text is not None:
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.PREMIUM,
            text=text,
            dedup_key=key,
            payload={"buttons": [{"text": "💎 Premium", "app_route": "premium"}]},
            priority=2,
        )


async def approve(session: AsyncSession, *, actor_id: uuid.UUID, payment_id: uuid.UUID) -> CardPayment:
    from app.services.premium import _extend
    from app.utils.timezone import format_date

    payment = await get(session, payment_id)
    # Two admins pressing «Tasdiqlash» at the same moment must not give Premium twice.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"card-payment:{payment.id}"))))
    await session.refresh(payment)
    if payment.status != CardPaymentStatus.PENDING:
        raise ConflictError("CARD_PAYMENT_DECIDED", "Bu to'lov allaqachon ko'rib chiqilgan.")
    payment.status = CardPaymentStatus.APPROVED
    payment.decided_at = datetime.now(UTC)
    payment.decided_by = actor_id
    if payment.kind == PaymentKind.PREMIUM:
        plan = await session.get(PremiumPlan, payment.plan_id) if payment.plan_id else None
        subscription = await _extend(
            session,
            user_id=payment.user_id,
            days=plan.days if plan else 30,
            source=PremiumSource.CARD,
            plan_id=plan.id if plan else None,
            granted_by=actor_id,
            note=f"Karta orqali to'lov: {format_uzs(payment.amount_uzs)}",
        )
        payment.subscription_id = subscription.id
        message = (
            f"✅ To'lovingiz tasdiqlandi — rahmat! Premium faollashtirildi: {format_date(subscription.ends_at)} gacha."
        )
    else:
        message = f"❤️ {format_uzs(payment.amount_uzs)} hissangiz qabul qilindi. Katta rahmat!"
    record_audit(
        session, actor_id=actor_id, action="CARD_PAYMENT_APPROVE", entity_type="card_payment", entity_id=payment.id
    )
    await _member_message(session, payment.user_id, message, f"card-payment:{payment.id}:approved")
    await session.commit()
    return payment


async def reject(session: AsyncSession, *, actor_id: uuid.UUID, payment_id: uuid.UUID, reason: str) -> CardPayment:
    payment = await get(session, payment_id)
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"card-payment:{payment.id}"))))
    await session.refresh(payment)
    if payment.status != CardPaymentStatus.PENDING:
        raise ConflictError("CARD_PAYMENT_DECIDED", "Bu to'lov allaqachon ko'rib chiqilgan.")
    payment.status = CardPaymentStatus.REJECTED
    payment.decided_at = datetime.now(UTC)
    payment.decided_by = actor_id
    payment.reject_reason = reason.strip()
    record_audit(
        session,
        actor_id=actor_id,
        action="CARD_PAYMENT_REJECT",
        entity_type="card_payment",
        entity_id=payment.id,
        reason=payment.reject_reason,
    )
    await _member_message(
        session,
        payment.user_id,
        f"To'lovingiz tasdiqlanmadi. Sabab: {payment.reject_reason}\nSavol bo'lsa — botda /paysupport.",
        f"card-payment:{payment.id}:rejected",
    )
    await session.commit()
    return payment


async def receipt(session: AsyncSession, payment: CardPayment) -> bytes:
    return await get_storage().get(payment.receipt_key)


async def list_payments(
    session: AsyncSession, *, status: CardPaymentStatus | None, limit: int, offset: int
) -> tuple[list[tuple[CardPayment, User, str | None]], int]:
    query = (
        select(CardPayment, User, PremiumPlan.title)
        .join(User, User.id == CardPayment.user_id)
        .outerjoin(PremiumPlan, PremiumPlan.id == CardPayment.plan_id)
    )
    if status is not None:
        query = query.where(CardPayment.status == status)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.execute(query.order_by(CardPayment.created_at.desc()).limit(limit).offset(offset))
    return [(payment, user, title) for payment, user, title in rows], int(total or 0)


async def member_payments(session: AsyncSession, user_id: uuid.UUID) -> list[tuple[CardPayment, str | None]]:
    rows = await session.execute(
        select(CardPayment, PremiumPlan.title)
        .outerjoin(PremiumPlan, PremiumPlan.id == CardPayment.plan_id)
        .where(CardPayment.user_id == user_id)
        .order_by(CardPayment.created_at.desc())
        .limit(10)
    )
    return [(payment, title) for payment, title in rows]


async def totals(session: AsyncSession) -> dict[str, Any]:
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def total(*conditions: Any) -> int:
        return int(
            await session.scalar(
                select(func.coalesce(func.sum(CardPayment.amount_uzs), 0)).where(
                    CardPayment.status == CardPaymentStatus.APPROVED, *conditions
                )
            )
            or 0
        )

    pending = await session.scalar(
        select(func.count()).select_from(CardPayment).where(CardPayment.status == CardPaymentStatus.PENDING)
    )
    return {
        "uzs_total": await total(),
        "uzs_this_month": await total(CardPayment.decided_at >= month_start),
        "card_pending": int(pending or 0),
    }
