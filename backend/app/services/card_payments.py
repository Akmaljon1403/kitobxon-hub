"""Paying to the club's bank card: Premium, Telegram Stars or a donation.

Telegram Stars are the automatic way to pay. Many students have no Stars (and do not know how to
buy them) but do have a local card, so they transfer the price to the club's card and send the
receipt (a screenshot). The super admin checks it and confirms in the bot or the Admin Panel:

* Premium switches on by itself (a personal discount, if any, lowers the price);
* Stars (for members who have none): Telegram does not let bots hand out Stars. After the super
  admin confirms, the order goes to the admins given «⭐ Stars yuborish» (STARS_SEND) — or to the
  super admins when nobody has it — with the steps to buy the Stars on Fragment for the member's
  @username (that is why a username is required); their «✅ Stars yuborildi» tells the member;
* a donation is recorded with thanks.

Every receipt goes to the payments chat (a private group or channel set by the super admin) with
the decision buttons, or — when no chat is set — to the super admins in the bot. Every step after
that (confirmed, rejected, undone, Stars ordered, Stars sent) is written in the payments chat too,
wherever it was taken. A decision taken by mistake can be undone for two days («↩️ Qaytarish»).

Nothing is charged by the bot: it only records.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import uuid
from datetime import UTC, datetime, timedelta
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

logger = logging.getLogger(__name__)

MAX_RECEIPT_BYTES = 10 * 1024 * 1024
MAX_PENDING = 3
MIN_DONATION_UZS = 1_000
UNDO_HOURS = 48
STARS_NEED_USERNAME = (
    "⭐ Stars'ni sizga sovg'a qilish uchun Telegram profilingizda username bo'lishi kerak: Telegram → "
    "Sozlamalar → «Foydalanuvchi nomi» (Username). Nom qo'ygach, qayta urinib ko'ring. Premium'ni esa "
    "username'siz ham karta orqali olish mumkin."
)


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
        if not user.telegram_username:
            raise ConflictError("STARS_NEED_USERNAME", STARS_NEED_USERNAME)
        package = next((item for item in await stars_offer(session) if item["stars"] == stars), None)
        if package is None:
            raise NotFoundError("STARS_PACKAGE_NOT_FOUND", "Bunday Stars to'plami sotilmaydi.")
        kind, amount = PaymentKind.STARS, package["price_uzs"]
    else:
        if amount_uzs is None or amount_uzs < MIN_DONATION_UZS:
            raise BadRequestError("INVALID_AMOUNT", f"Hissa kamida {format_uzs(MIN_DONATION_UZS)} bo'lsin.")
        kind, amount = PaymentKind.DONATION, amount_uzs
    prepared = await asyncio.to_thread(prepare_receipt, receipt)
    fingerprint = hashlib.sha256(receipt).hexdigest()
    key = f"card-receipts/{user.id}/{uuid.uuid4().hex}.jpg"
    await get_storage().put(key, prepared, "image/jpeg")
    assert amount is not None
    payment = CardPayment(
        user_id=user.id,
        kind=kind,
        plan_id=plan.id if plan else None,
        amount_uzs=amount,
        receipt_key=key,
        receipt_sha256=fingerprint,
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
    await session.commit()
    await _tell_admins(session, payment, user, plan)
    return payment


def staff_text(payment: CardPayment, user: User, plan_title: str | None) -> str:
    """The receipt's caption for the admins (HTML)."""
    import html

    if payment.kind == PaymentKind.PREMIUM:
        what = f"💎 Premium «{html.escape(plan_title or '—')}»"
    elif payment.kind == PaymentKind.STARS:
        what = f"⭐ {payment.stars} Telegram Stars"
    else:
        what = "❤️ Hissa"
    return (
        f"💳 <b>Yangi karta to'lovi</b>\n\n{what} — <b>{format_uzs(payment.amount_uzs)}</b>\n"
        f"A'zo: {html.escape(user.last_name)} {html.escape(user.first_name)}"
        + (f" (@{html.escape(user.telegram_username)})" if user.telegram_username else "")
        + "\n\nChekni ko'rib, tasdiqlang yoki rad eting."
    )


def decision_markup(payment: CardPayment, *, with_receipt: bool = False) -> Any:
    from app.bot import keyboards

    return keyboards.card_decision(payment.id.hex, view=with_receipt)


async def payments_chat(session: AsyncSession) -> str | None:
    from app.services import payments_chat as chat_service

    return await chat_service.chat_id(session)


async def _send_to_chat(session: AsyncSession, payment: CardPayment, text: str) -> bool:
    """The receipt with its buttons in the payments chat. False when there is no chat or it failed."""
    from aiogram.types import BufferedInputFile

    from app.services.delivery import optional_bot

    chat = await payments_chat(session)
    bot = optional_bot() if chat else None
    if chat is None or bot is None:
        return False
    try:
        sent = await bot.send_photo(
            chat,
            BufferedInputFile(await receipt(session, payment), filename="chek.jpg"),
            caption=text,
            reply_markup=decision_markup(payment),
        )
    except Exception:
        logger.warning("The payments chat could not be reached; the super admins are told in the bot")
        return False
    from app.services import payments_chat as chat_service

    try:
        await chat_service.remember(session, sent, ("card", payment.id, payment.user_id))
    except Exception:  # the receipt is out; only the «Reply» shortcut is lost
        logger.exception("A payments chat link could not be stored")
        await session.rollback()
    return True


async def earlier_copy(session: AsyncSession, payment: CardPayment) -> str | None:
    """A warning when the very same receipt file was sent before (by this member or anyone else)."""
    import html

    from app.utils.timezone import format_datetime

    if not payment.receipt_sha256:
        return None
    row = (
        await session.execute(
            select(CardPayment, User)
            .join(User, User.id == CardPayment.user_id)
            .where(CardPayment.receipt_sha256 == payment.receipt_sha256, CardPayment.id != payment.id)
            .order_by(CardPayment.created_at)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    earlier, owner = row
    status = {
        CardPaymentStatus.APPROVED: "tasdiqlangan",
        CardPaymentStatus.REJECTED: "rad etilgan",
        CardPaymentStatus.PENDING: "tekshirilmoqda",
    }.get(earlier.status, str(earlier.status))
    who = (
        "shu a'zo" if owner.id == payment.user_id else f"{html.escape(owner.last_name)} {html.escape(owner.first_name)}"
    )
    return (
        f"⚠️ <b>Diqqat: bu chek avval ham yuborilgan</b> — {format_datetime(earlier.created_at)}, {who}, "
        f"{format_uzs(earlier.amount_uzs)} ({status}). Bank ilovasida tekshirib ko'ring."
    )


async def _tell_admins(session: AsyncSession, payment: CardPayment, user: User, plan: PremiumPlan | None) -> None:
    from app.services.rbac import super_admins

    text = staff_text(payment, user, plan.title if plan else None)
    warning = await earlier_copy(session, payment)
    if warning:
        text = f"{text}\n\n{warning}"
    if await _send_to_chat(session, payment, text):
        return
    await enqueue_for_members(
        session,
        type_=NotificationType.PREMIUM,
        text=text,
        dedup_prefix=f"card-payment:{payment.id}",
        members=super_admins(),
        sync=f"card:{payment.id}",
        payload={
            "base": text,
            "buttons": [
                {"text": "🧾 Chekni ko'rish", "callback": f"cp:view:{payment.id.hex}"},
                {
                    "row": [
                        {"text": "✅ Tasdiqlash", "callback": f"cp:ok:{payment.id.hex}"},
                        {"text": "❌ Rad etish", "callback": f"cp:no:{payment.id.hex}"},
                    ]
                },
            ],
        },
        priority=2,
    )
    await session.commit()


# ---------------------------------------------------------------------------- the payments chat and Stars orders


def _e(value: str) -> str:
    import html

    return html.escape(value, quote=False)


async def _what(session: AsyncSession, payment: CardPayment) -> str:
    if payment.kind == PaymentKind.PREMIUM:
        plan = await session.get(PremiumPlan, payment.plan_id) if payment.plan_id else None
        return f"💎 Premium «{_e(plan.title if plan else '—')}»"
    if payment.kind == PaymentKind.STARS:
        return f"⭐ {payment.stars} Telegram Stars"
    return "❤️ Hissa"


async def _name(session: AsyncSession, user_id: uuid.UUID | None) -> str:
    user = await session.get(User, user_id) if user_id else None
    return _e(f"{user.first_name} {user.last_name}".strip()) if user else "—"


async def stars_sender_ids(session: AsyncSession) -> list[uuid.UUID]:
    """Who gifts the Stars of a confirmed order: the admins given «⭐ Stars yuborish», or — when nobody
    has that right — the super admins themselves."""
    from app.security.permissions import Perm
    from app.services.rbac import admins_with_permission, super_admins

    holders = set(await session.scalars(admins_with_permission(Perm.STARS_SEND)))
    bosses = set(await session.scalars(super_admins()))
    return sorted(holders - bosses) or sorted(bosses)


async def stars_senders_text(session: AsyncSession) -> str:
    names = [await _name(session, user_id) for user_id in await stars_sender_ids(session)]
    return ", ".join(names) or "—"


async def chat_line(session: AsyncSession, payment: CardPayment, headline: str, *details: str) -> None:
    """One step of a payment, written in the payments chat (when one is set)."""
    from app.services import payments_chat as chat_service

    user = await session.get(User, payment.user_id)
    who = await chat_service._who(session, user) if user else ""
    parts = [f"{headline} — {await _what(session, payment)}, <b>{format_uzs(payment.amount_uzs)}</b>", who, *details]
    await chat_service.post(
        session, "\n".join(part for part in parts if part), link=("card", payment.id, payment.user_id)
    )


async def _order_stars(session: AsyncSession, payment: CardPayment, boss_id: uuid.UUID) -> None:
    """The confirmed Stars order goes to whoever gifts the Stars, with the steps and «✅ Stars yuborildi»."""
    from app.utils.timezone import format_datetime

    user = await session.get(User, payment.user_id)
    if user is None:
        return
    ids = await stars_sender_ids(session)
    if not ids:
        return
    member = _e(f"{user.last_name} {user.first_name}")
    text = (
        f"✅ <b>Bosh admin tomonidan tasdiqlandi</b> — {await _name(session, boss_id)}, "
        f"{format_datetime(payment.decided_at or datetime.now(UTC))}\n"
        f"<b>{member}</b> ga <b>⭐ {payment.stars} Stars</b> kerak (karta orqali to'langan: "
        f"{format_uzs(payment.amount_uzs)}).\n\n{gift_steps(payment, user)}"
    )
    await enqueue_for_members(
        session,
        type_=NotificationType.PREMIUM,
        text=text,
        dedup_prefix=f"stars-order:{payment.id}:{_stamp(payment)}",
        members=select(User.id).where(User.id.in_(ids)),
        sync=f"stars:{payment.id}",
        payload={"base": text, "buttons": [{"text": "✅ Stars yuborildi", "callback": f"cp:sent:{payment.id.hex}"}]},
        priority=1,
    )


async def _cancel_stars_order(session: AsyncSession, payment: CardPayment) -> None:
    ids = await stars_sender_ids(session)
    user = await session.get(User, payment.user_id)
    if not ids or user is None:
        return
    await enqueue_for_members(
        session,
        type_=NotificationType.PREMIUM,
        text=(
            f"↩️ <b>Stars buyurtmasi qaytarildi</b>: {_e(user.last_name)} {_e(user.first_name)} — "
            f"⭐ {payment.stars} Stars. Hozircha yubormang: bosh admin chekni qayta ko'rib chiqmoqda."
        ),
        dedup_prefix=f"stars-order-undo:{payment.id}:{int(datetime.now(UTC).timestamp())}",
        members=select(User.id).where(User.id.in_(ids)),
        priority=1,
    )


async def _auto_deliver_stars(session: AsyncSession, payment: CardPayment) -> bool:
    """Try to deliver a confirmed Stars order through the provider (if one is connected and enabled).

    Returns True when the provider accepted it — the order is then marked delivered and the member is
    told. On anything missing or wrong (no provider, switched off, no username, or a provider error)
    returns False, so the caller falls back to the manual admin flow and the member still gets Stars."""
    from app.services import stars_provider

    if not stars_provider.configured() or not await get_setting(session, "payments.stars_auto_deliver"):
        return False
    user = await session.get(User, payment.user_id)
    if user is None or not user.telegram_username or not payment.stars:
        return False
    try:
        result = await stars_provider.send_stars(
            user.telegram_username, payment.stars, idempotency_key=f"stars:{payment.id}"
        )
    except stars_provider.StarsProviderError as exc:
        logger.warning("Automatic Stars delivery failed for %s; falling back to manual: %s", payment.id, exc)
        return False
    payment.delivered_at = datetime.now(UTC)
    payment.delivered_by = None  # the provider delivered it, not an admin
    request_ref = str(result.get("request_id") or result.get("id") or "")[:64]
    record_audit(
        session,
        actor_id=payment.decided_by,
        action="CARD_STARS_AUTO_DELIVERED",
        entity_type="card_payment",
        entity_id=payment.id,
        after={"stars": payment.stars, "request_id": request_ref or None},
    )
    await _member_message(
        session,
        payment.user_id,
        f"⭐ {payment.stars} Stars sizga avtomatik yuborildi! Ularni Telegram → Sozlamalar → Telegram Stars "
        "bo'limida ko'rasiz. Endi Premium'ni ham bir bosishda olishingiz mumkin. Rahmat!",
        f"card-payment:{payment.id}:delivered",
    )
    return True


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


async def _settle_card(session: AsyncSession, payment: CardPayment, status: str) -> None:
    """Every super admin's copy of the receipt shows the decision (whoever took it, wherever)."""
    from app.services import copies

    hexed = payment.id.hex
    if payment.status == CardPaymentStatus.PENDING:
        buttons: list[dict[str, Any]] = [
            {"text": "🧾 Chekni ko'rish", "callback": f"cp:view:{hexed}"},
            {
                "row": [
                    {"text": "✅ Tasdiqlash", "callback": f"cp:ok:{hexed}"},
                    {"text": "❌ Rad etish", "callback": f"cp:no:{hexed}"},
                ]
            },
        ]
    else:
        buttons = [{"text": "🧾 Chekni ko'rish", "callback": f"cp:view:{hexed}"}]
        if (
            payment.kind == PaymentKind.STARS
            and payment.status == CardPaymentStatus.APPROVED
            and not payment.delivered_at
        ):
            buttons.append({"text": "✅ Stars yuborildi", "callback": f"cp:sent:{hexed}"})
        if payment.delivered_at is None:
            buttons.append({"text": "↩️ Qaytarish", "callback": f"cp:undo:{hexed}"})
    await copies.settle(session, f"card:{payment.id}", status, buttons=buttons)


def _stamp(payment: CardPayment) -> int:
    """Makes the member's message keys unique again after a decision was undone and taken anew."""
    return int((payment.decided_at or datetime.now(UTC)).timestamp() * 1_000_000)


async def approve(
    session: AsyncSession, *, actor_id: uuid.UUID, payment_id: uuid.UUID, announce: bool = True
) -> CardPayment:
    """``announce``: write the decision in the payments chat (False when it was taken there and the
    receipt message itself shows it)."""
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
    await _member_message(session, payment.user_id, message, f"card-payment:{payment.id}:approved:{_stamp(payment)}")
    auto_sent = False
    if payment.kind == PaymentKind.STARS:
        # When a Stars provider is connected, send automatically; otherwise hand it to an admin to gift.
        auto_sent = await _auto_deliver_stars(session, payment)
        if not auto_sent:
            await _order_stars(session, payment, actor_id)
    from app.services import copies

    def _stars_note() -> str:
        return "⭐ Avtomatik yuborildi" if auto_sent else f"⭐ Yuborish topshirildi: {await_senders}"

    await_senders = await stars_senders_text(session) if payment.kind == PaymentKind.STARS and not auto_sent else ""
    status = f"✅ <b>Tasdiqlandi</b> — {await _name(session, actor_id)}, {copies.stamp()}"
    if payment.kind == PaymentKind.STARS:
        status += f"\n{_stars_note()}"
    await _settle_card(session, payment, status)
    await session.commit()
    if announce:
        details = [f"Qaror: {await _name(session, actor_id)}"]
        if payment.kind == PaymentKind.STARS:
            details.append(_stars_note())
        await chat_line(session, payment, "✅ <b>Tasdiqlandi</b>", *details)
    return payment


def gift_steps(payment: CardPayment, user: User) -> str:
    """What the admin does after confirming a Stars purchase: buy them on Fragment for the member (HTML)."""
    import html

    who = f'<a href="tg://user?id={user.telegram_id}">{html.escape(user.last_name)} {html.escape(user.first_name)}</a>'
    username = f"@{html.escape(user.telegram_username)}" if user.telegram_username else "—"
    return (
        f"⭐ <b>Endi {payment.stars} Stars'ni yuboring</b>\n\n"
        f"Kimga: {who}\nUsername: <code>{username}</code>\n\n"
        '1. <a href="https://fragment.com/stars/buy">fragment.com/stars/buy</a> sahifasini oching '
        "(Telegram yoki TON hamyoningiz bilan kiring).\n"
        f"2. «Recipient» maydoniga <code>{username}</code> ni yozing, miqdor — <b>{payment.stars}</b>.\n"
        "3. To'lovni tasdiqlang: Stars bir necha daqiqada a'zoning Telegram hisobiga tushadi.\n"
        "4. So'ng pastdagi <b>«✅ Stars yuborildi»</b> tugmasini bosing — a'zoga xabar boradi.\n\n"
        "Fragment ishlamasa: a'zo profilida ⋮ → 🎁 Sovg'a yuborish → ⭐ Stars ham bo'ladi. Bot buni o'zi "
        "qila olmaydi: Telegram botlarga Stars berishga ruxsat bermaydi."
    )


async def mark_delivered(
    session: AsyncSession, *, actor_id: uuid.UUID, payment_id: uuid.UUID, announce: bool = True
) -> CardPayment:
    """The admin gifted the Stars in Telegram: the member is told (and the payments chat)."""
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
    from app.services import copies

    done = f"⭐ <b>Stars yuborildi</b> — {await _name(session, actor_id)}, {copies.stamp()}"
    await copies.settle(session, f"stars:{payment.id}", done, buttons=[])
    await _settle_card(session, payment, f"✅ Tasdiqlangan · {done}")
    await session.commit()
    if announce:
        sender = await _name(session, actor_id)
        await chat_line(session, payment, "⭐ <b>Stars yuborildi</b>", f"Yubordi: {sender} · a'zoga xabar berildi")
    return payment


async def reject(
    session: AsyncSession, *, actor_id: uuid.UUID, payment_id: uuid.UUID, reason: str, announce: bool = True
) -> CardPayment:
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
        f"card-payment:{payment.id}:rejected:{_stamp(payment)}",
    )
    from app.services import copies

    await _settle_card(
        session,
        payment,
        f"❌ <b>Rad etildi</b> — {await _name(session, actor_id)}, {copies.stamp()}\n"
        f"Sabab: {_e(payment.reject_reason or '—')}",
    )
    await session.commit()
    if announce:
        await chat_line(
            session,
            payment,
            "❌ <b>Rad etildi</b>",
            f"Sabab: {_e(payment.reject_reason or '—')}",
            f"Qaror: {await _name(session, actor_id)}",
        )
    return payment


async def undo(
    session: AsyncSession, *, actor_id: uuid.UUID, payment_id: uuid.UUID, announce: bool = True
) -> CardPayment:
    """«↩️ Qaytarish»: a decision taken by mistake goes back to «waiting» (for two days).
    A confirmed Premium is taken back; Stars already gifted cannot be taken back."""
    from app.services.premium import cancel_period

    payment = await get(session, payment_id)
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"card-payment:{payment.id}"))))
    await session.refresh(payment)
    if payment.status == CardPaymentStatus.PENDING:
        raise ConflictError("CARD_PAYMENT_PENDING", "Bu to'lov hali ko'rib chiqilmagan.")
    if payment.decided_at is not None and payment.decided_at < datetime.now(UTC) - timedelta(hours=UNDO_HOURS):
        raise ConflictError("UNDO_TOO_LATE", f"Qarorga {UNDO_HOURS} soatdan oshdi — endi qaytarib bo'lmaydi.")
    if payment.delivered_at is not None:
        raise ConflictError("STARS_DELIVERED", "Stars allaqachon yuborilgan — qarorni qaytarib bo'lmaydi.")
    previous = payment.status
    if previous == CardPaymentStatus.APPROVED and payment.subscription_id is not None:
        await cancel_period(session, payment.subscription_id)
        payment.subscription_id = None
        if payment.discount_id is not None:
            from app.models import PremiumDiscount

            discount = await session.get(PremiumDiscount, payment.discount_id)
            if discount is not None and discount.used_for == f"card:{payment.id}":
                discount.used_at = None
                discount.used_for = None
    stamp = _stamp(payment)
    payment.status = CardPaymentStatus.PENDING
    payment.decided_at = None
    payment.decided_by = None
    payment.reject_reason = None
    record_audit(
        session,
        actor_id=actor_id,
        action="CARD_PAYMENT_UNDO",
        entity_type="card_payment",
        entity_id=payment.id,
        before={"status": str(previous)},
    )
    await _member_message(
        session,
        payment.user_id,
        "↩️ Avvalgi xabarimiz xato edi — kechirasiz! Chekingiz qayta tekshirilmoqda, natijasini tez orada "
        "shu yerda xabar qilamiz.",
        f"card-payment:{payment.id}:undo:{stamp}",
    )
    if previous == CardPaymentStatus.APPROVED and payment.kind == PaymentKind.STARS:
        await _cancel_stars_order(session, payment)
        from app.services import copies

        await copies.settle(session, f"stars:{payment.id}", "↩️ <b>Buyurtma qaytarildi</b> — yubormang", buttons=[])
    from app.services import copies

    await _settle_card(
        session,
        payment,
        f"↩️ <b>Qaror qaytarildi</b> — {await _name(session, actor_id)}, {copies.stamp()}: qayta ko'rib chiqing",
    )
    await session.commit()
    if announce:
        admin = await _name(session, actor_id)
        await chat_line(session, payment, "↩️ <b>Qaror qaytarildi</b>", f"{admin} · chek qayta ko'rib chiqiladi")
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


async def repeated_receipts(session: AsyncSession, payments: list[CardPayment]) -> set[uuid.UUID]:
    """Which of these payments carry a receipt file that was also sent with another payment."""
    hashes = {payment.receipt_sha256 for payment in payments if payment.receipt_sha256}
    if not hashes:
        return set()
    repeated = set(
        await session.scalars(
            select(CardPayment.receipt_sha256)
            .where(CardPayment.receipt_sha256.in_(hashes))
            .group_by(CardPayment.receipt_sha256)
            .having(func.count(CardPayment.id) > 1)
        )
    )
    return {payment.id for payment in payments if payment.receipt_sha256 in repeated}


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
