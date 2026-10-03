"""Paying to the club's bank card: Premium, Telegram Stars or a donation.

Telegram Stars are the automatic way to pay. Many students have no Stars (and do not know how to
buy them) but do have a local card, so they transfer the price to the club's card and send the
receipt (a screenshot). The super admin checks it and confirms in the bot or the Admin Panel:

* Premium switches on by itself (a personal discount, if any, lowers the price);
* Stars: Telegram does not let bots hand out Stars, so after confirming the bot shows the admin
  the member's profile and the steps to gift the Stars in Telegram (Telegram charges the admin's
  card and the Stars go to the member), then «✅ Yuborildi» tells the member;
* a donation is recorded with thanks.

Nothing is charged by the bot: it only records.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import UTC, datetime
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import and_, func, or_, select
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


def discounted_uzs(price: int | None, percent: int | None) -> int | None:
    """A so'm price after a personal discount, rounded to 100 so'm."""
    if price is None or not percent:
        return price
    return max(100, round(price * (100 - percent) / 100 / 100) * 100)


async def stars_offer(session: AsyncSession) -> list[dict[str, int]]:
    """Stars packages sold for so'm (empty when card payments are off or no packages are set)."""
    if await card_details(session) is None:
        return []
    rate = int(await get_setting(session, "payments.star_price_uzs"))
    packages: list[int] = await get_setting(session, "payments.stars_packages")
    if rate <= 0:
        return []
    # Rounded up to 500 so'm, so the transfer is an easy number.
    return [
        {"stars": stars, "price_uzs": -(-stars * rate // 500) * 500} for stars in sorted(set(packages)) if stars > 0
    ]


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
    stars: int | None = None,
) -> CardPayment:
    """The member says "I paid": a plan (its card price), a Stars package or a donation of ``amount_uzs``."""
    if await card_details(session) is None:
        raise ConflictError("CARD_PAYMENTS_OFF", "Karta orqali to'lov hozircha yoqilmagan.")
    pending = await session.scalar(
        select(func.count())
        .select_from(CardPayment)
        .where(CardPayment.user_id == user.id, CardPayment.status == CardPaymentStatus.PENDING)
    )
    if (pending or 0) >= MAX_PENDING:
        raise ConflictError("TOO_MANY_PENDING", "Avvalgi cheklaringiz hali tekshirilmoqda. Biroz kuting.")
    from app.services.premium import active_discount

    plan = None
    discount = None
    if plan_id is not None:
        plan = await session.get(PremiumPlan, plan_id)
        if plan is None or not plan.is_active or not plan.price_uzs:
            raise NotFoundError("PLAN_NOT_FOUND", "Bu tarif karta orqali sotilmaydi.")
        discount = await active_discount(session, user.id)
        kind, amount = PaymentKind.PREMIUM, discounted_uzs(plan.price_uzs, discount.percent if discount else None)
    elif stars is not None:
        package = next((item for item in await stars_offer(session) if item["stars"] == stars), None)
        if package is None:
            raise NotFoundError("STARS_PACKAGE_NOT_FOUND", "Bunday Stars to'plami sotilmaydi.")
        kind, amount = PaymentKind.STARS, package["price_uzs"]
    else:
        if amount_uzs is None or amount_uzs < MIN_DONATION_UZS:
            raise BadRequestError("INVALID_AMOUNT", f"Hissa kamida {format_uzs(MIN_DONATION_UZS)} bo'lsin.")
        kind, amount = PaymentKind.DONATION, amount_uzs
    prepared = await asyncio.to_thread(prepare_receipt, receipt)
    key = f"card-receipts/{user.id}/{uuid.uuid4().hex}.jpg"
    await get_storage().put(key, prepared, "image/jpeg")
    assert amount is not None
    payment = CardPayment(
        user_id=user.id,
        kind=kind,
        plan_id=plan.id if plan else None,
        amount_uzs=amount,
        receipt_key=key,
        stars=stars if kind == PaymentKind.STARS else None,
        discount_id=discount.id if discount else None,
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

    if plan:
        what = f"💎 Premium «{plan.title}»"
    elif payment.kind == PaymentKind.STARS:
        what = f"⭐ {payment.stars} Telegram Stars"
    else:
        what = "❤️ Hissa"
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
        if payment.discount_id is not None:
            from app.models import PremiumDiscount

            discount = await session.get(PremiumDiscount, payment.discount_id)
            if discount is not None and discount.used_at is None:
                discount.used_at = datetime.now(UTC)
                discount.used_for = f"card:{payment.id}"
        message = (
            f"✅ To'lovingiz tasdiqlandi — rahmat! Premium faollashtirildi: {format_date(subscription.ends_at)} gacha."
        )
    elif payment.kind == PaymentKind.STARS:
        message = (
            f"✅ To'lovingiz tasdiqlandi! ⭐ {payment.stars} Stars tez orada Telegram'da sizga sovg'a sifatida "
            "yuboriladi — tushishi bilan xabar beramiz."
        )
    else:
        message = f"❤️ {format_uzs(payment.amount_uzs)} hissangiz qabul qilindi. Katta rahmat!"
    record_audit(
        session, actor_id=actor_id, action="CARD_PAYMENT_APPROVE", entity_type="card_payment", entity_id=payment.id
    )
    await _member_message(session, payment.user_id, message, f"card-payment:{payment.id}:approved")
    await session.commit()
    return payment


def gift_steps(payment: CardPayment, user: User) -> str:
    """What the admin does in Telegram after confirming a Stars purchase (HTML)."""
    import html

    who = f'<a href="tg://user?id={user.telegram_id}">{html.escape(user.last_name)} {html.escape(user.first_name)}</a>'
    if user.telegram_username:
        who += f" (@{html.escape(user.telegram_username)})"
    return (
        f"⭐ <b>Endi {payment.stars} Stars'ni sovg'a qiling</b>\n\n"
        f"Kimga: {who}\n\n"
        "1. Ismni bosib, a'zoning profilini oching (yoki qidiruvda @username).\n"
        "2. Profil menyusi (⋮) → <b>🎁 Sovg'a yuborish</b> → <b>⭐ Stars</b> "
        f"(yoki Sozlamalar → Telegram Stars → «Stars sovg'a qilish») → <b>{payment.stars} ⭐</b>.\n"
        "3. Telegram to'lovni kartangizdan oladi, Stars esa to'g'ridan-to'g'ri a'zoning hisobiga tushadi.\n"
        "4. So'ng pastdagi <b>«✅ Stars yuborildi»</b> tugmasini bosing — a'zoga xabar boradi.\n\n"
        "Bot buni o'zi qila olmaydi: Telegram botlarga Stars berishga ruxsat bermaydi."
    )


async def mark_delivered(session: AsyncSession, *, actor_id: uuid.UUID, payment_id: uuid.UUID) -> CardPayment:
    """The admin gifted the Stars in Telegram: the member is told."""
    payment = await get(session, payment_id)
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"card-payment:{payment.id}"))))
    await session.refresh(payment)
    if payment.kind != PaymentKind.STARS or payment.status != CardPaymentStatus.APPROVED:
        raise ConflictError("NOT_STARS_TO_DELIVER", "Bu to'lov Stars sovg'asi emas yoki hali tasdiqlanmagan.")
    if payment.delivered_at is not None:
        raise ConflictError("STARS_DELIVERED", "Stars allaqachon yuborilgan deb belgilangan.")
    payment.delivered_at = datetime.now(UTC)
    payment.delivered_by = actor_id
    record_audit(
        session, actor_id=actor_id, action="CARD_STARS_DELIVERED", entity_type="card_payment", entity_id=payment.id
    )
    await _member_message(
        session,
        payment.user_id,
        f"⭐ {payment.stars} Stars sizga sovg'a qilindi! Ularni Telegram → Sozlamalar → Telegram Stars bo'limida "
        "ko'rasiz. Endi Premium'ni ham bir bosishda olishingiz mumkin. Rahmat!",
        f"card-payment:{payment.id}:delivered",
    )
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
    if status == CardPaymentStatus.PENDING:
        # "Waiting for me": receipts to check and confirmed Stars still to be gifted.
        query = query.where(
            or_(
                CardPayment.status == CardPaymentStatus.PENDING,
                and_(
                    CardPayment.kind == PaymentKind.STARS,
                    CardPayment.status == CardPaymentStatus.APPROVED,
                    CardPayment.delivered_at.is_(None),
                ),
            )
        )
    elif status is not None:
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
    undelivered = await session.scalar(
        select(func.count())
        .select_from(CardPayment)
        .where(
            CardPayment.kind == PaymentKind.STARS,
            CardPayment.status == CardPaymentStatus.APPROVED,
            CardPayment.delivered_at.is_(None),
        )
    )
    return {
        "uzs_total": await total(),
        "uzs_this_month": await total(CardPayment.decided_at >= month_start),
        "card_pending": int(pending or 0) + int(undelivered or 0),
    }
