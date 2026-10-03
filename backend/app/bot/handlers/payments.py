"""Premium and donations with Telegram Stars, plus /terms and /paysupport (required for payments)."""

from __future__ import annotations

import html
import logging
import uuid
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, texts
from app.bot.states import CardDonationAmount, CardReceipt, CardReject
from app.core.errors import AppError
from app.models import User
from app.models.enums import FeatureMode, PaymentKind, UserStatus
from app.services import card_payments, features
from app.services import premium as premium_service
from app.utils.timezone import format_date

logger = logging.getLogger(__name__)
router = Router(name="payments")


def _active(member: User | None) -> bool:
    return member is not None and member.status == UserStatus.ACTIVE


async def _premium_text(db: AsyncSession, member: User) -> str:
    status = await premium_service.member_status(db, member)
    if status["lifetime"]:
        current = texts.PREMIUM_STATUS_LIFETIME
    elif status["is_premium"] and status["until"]:
        current = texts.PREMIUM_STATUS_ON.format(until=format_date(status["until"]))
    else:
        current = texts.PREMIUM_STATUS_OFF
    if status["discount"]:
        current += "\n" + texts.PREMIUM_DISCOUNT.format(
            percent=status["discount"]["percent"], until=format_date(status["discount"]["valid_until"])
        )
    perks = [
        texts.PREMIUM_PERK.format(title=f["title"], description=f["description"]) for f in status["premium_features"]
    ]
    perks += [
        texts.PREMIUM_PERK.format(title=f"{perk['icon']} {perk['title']}", description=perk["description"])
        for perk in status["perks"]
    ]
    return texts.PREMIUM_INFO.format(status=current, perks="\n".join(perks))


async def show_premium(message: Message, db: AsyncSession, member: User) -> None:
    if await features.mode(db, "premium") == FeatureMode.OFF:
        await message.answer(texts.PREMIUM_CLOSED)
        return
    plans = await premium_service.list_plans(db)
    donations = await features.mode(db, "donations") != FeatureMode.OFF
    discount = await premium_service.active_discount(db, member.id)

    def label(plan: Any) -> str:
        if discount is None:
            return texts.PREMIUM_PLAN.format(title=plan.title, stars=plan.stars)
        stars = premium_service.discounted(plan.stars, discount.percent)
        return texts.PREMIUM_PLAN_DISCOUNT.format(title=plan.title, stars=stars, percent=discount.percent)

    await message.answer(
        await _premium_text(db, member),
        reply_markup=keyboards.premium_plans(
            [(plan.id.hex, label(plan)) for plan in plans],
            donations=donations,
            card=await card_payments.card_details(db) is not None,
            trial_days=await premium_service.trial_days(db, member),
        ),
    )


@router.message(Command("premium"))
@router.message(F.text == texts.BTN_PREMIUM)
async def premium_command(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if not _active(member):
        await message.answer(texts.NOT_REGISTERED)
        return
    assert member is not None
    await state.clear()  # pressed while writing to the admins or waiting for a photo
    await show_premium(message, db, member)


@router.callback_query(F.data == "prem:open")
async def premium_open(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if _active(member) and isinstance(callback.message, Message):
        assert member is not None
        await show_premium(callback.message, db, member)


@router.callback_query(F.data.startswith("prem:buy:"))
async def premium_buy(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if not _active(member) or not isinstance(callback.message, Message) or callback.bot is None:
        await callback.answer()
        return
    assert member is not None
    try:
        plan_id = uuid.UUID(hex=(callback.data or "").removeprefix("prem:buy:"))
        if await features.mode(db, "premium") == FeatureMode.OFF:
            raise features.FeatureOffError(features.get_feature("premium"))
        plan = await premium_service.get_plan(db, plan_id)
    except (ValueError, AppError) as exc:
        await callback.answer(getattr(exc, "message", texts.PREMIUM_CLOSED), show_alert=True)
        return
    await callback.answer()
    discount = await premium_service.active_discount(db, member.id)
    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id, **premium_service.plan_invoice(plan, member, discount)
    )


@router.callback_query(F.data == "prem:trial")
async def premium_trial(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if not _active(member) or not isinstance(callback.message, Message):
        await callback.answer()
        return
    assert member is not None
    try:
        subscription = await premium_service.start_trial(db, member)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await callback.answer("🎉")
    days = (subscription.ends_at - subscription.starts_at).days
    await callback.message.answer(
        texts.TRIAL_STARTED.format(days=days, until=format_date(subscription.ends_at)),
        reply_markup=await access.menu(db, member),
    )


@router.callback_query(F.data == "don:open")
async def donate_open(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if not _active(member) or not isinstance(callback.message, Message):
        return
    if await features.mode(db, "donations") == FeatureMode.OFF:
        await callback.message.answer(texts.DONATE_CLOSED)
        return
    await callback.message.answer(
        texts.DONATE_INFO, reply_markup=keyboards.donation_amounts(list(premium_service.DONATION_AMOUNTS))
    )


@router.callback_query(F.data.regexp(r"^don:\d+$"))
async def donate_amount(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if not _active(member) or not isinstance(callback.message, Message) or callback.bot is None:
        await callback.answer()
        return
    assert member is not None
    amount = int((callback.data or "").removeprefix("don:"))
    if await features.mode(db, "donations") == FeatureMode.OFF or amount not in premium_service.DONATION_AMOUNTS:
        await callback.answer(texts.DONATE_CLOSED, show_alert=True)
        return
    await callback.answer()
    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id, **premium_service.donation_invoice(amount, member)
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, db: AsyncSession) -> None:
    """Telegram waits at most 10 seconds for this answer before the Stars are taken."""
    error = await premium_service.check_pre_checkout(
        db,
        telegram_user_id=query.from_user.id,
        payload=query.invoice_payload,
        currency=query.currency,
        total_amount=query.total_amount,
    )
    if error is None:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message=error)


@router.message(F.successful_payment)
async def successful_payment(message: Message, db: AsyncSession) -> None:
    payment = message.successful_payment
    assert payment is not None and message.from_user is not None
    try:
        stored, subscription, _ = await premium_service.record_payment(
            db,
            telegram_user_id=message.from_user.id,
            payload=payment.invoice_payload,
            currency=payment.currency,
            total_amount=payment.total_amount,
            charge_id=payment.telegram_payment_charge_id,
        )
    except AppError:
        logger.exception("Payment %s could not be recorded", payment.telegram_payment_charge_id)
        await message.answer(texts.PAYMENT_STUCK)
        return
    if stored.kind == PaymentKind.PREMIUM and subscription is not None:
        await message.answer(texts.PAYMENT_PREMIUM_OK.format(until=format_date(subscription.ends_at)))
    else:
        await message.answer(texts.PAYMENT_DONATION_OK.format(amount=html.escape(str(stored.amount))))


@router.message(Command("terms"))
async def terms(message: Message) -> None:
    await message.answer(texts.TERMS)


@router.message(Command("paysupport"))
async def paysupport(message: Message, member: User | None) -> None:
    markup = keyboards.help_menu(support=True) if _active(member) else None
    await message.answer(texts.PAYSUPPORT, reply_markup=markup)


# ---------------------------------------------------------------------------- card payments (member)


@router.callback_query(F.data == "card:open")
async def card_open(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if not _active(member) or not isinstance(callback.message, Message):
        return
    if await card_payments.card_details(db) is None:
        await callback.message.answer(texts.CARD_OFF)
        return
    assert member is not None
    discount = await premium_service.active_discount(db, member.id)
    store_open = await features.mode(db, "premium") != FeatureMode.OFF
    plans = [plan for plan in await premium_service.list_plans(db) if plan.price_uzs] if store_open else []
    labels = []
    for plan in plans:
        price = card_payments.discounted_uzs(plan.price_uzs, discount.percent if discount else None)
        assert price is not None
        labels.append((plan.id.hex, texts.CARD_PLAN.format(title=plan.title, price=card_payments.format_uzs(price))))
    stars = [
        (item["stars"], texts.CARD_STARS.format(stars=item["stars"], price=card_payments.format_uzs(item["price_uzs"])))
        for item in await card_payments.stars_offer(db)
    ]
    await callback.message.answer(texts.CARD_CHOOSE, reply_markup=keyboards.card_plans(labels, stars))


async def _instructions(message: Message, db: AsyncSession, what: str, price: str) -> bool:
    card = await card_payments.card_details(db)
    if card is None:
        await message.answer(texts.CARD_OFF)
        return False
    await message.answer(
        texts.CARD_INSTRUCTIONS.format(
            what=html.escape(what),
            price=price,
            number=html.escape(card["number"]),
            holder=texts.CARD_HOLDER.format(holder=html.escape(card["holder"])) if card["holder"] else "",
        )
    )
    return True


@router.callback_query(F.data.startswith("card:plan:"))
async def card_plan(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if not _active(member) or not isinstance(callback.message, Message):
        return
    try:
        plan = await premium_service.get_plan(db, uuid.UUID(hex=(callback.data or "").removeprefix("card:plan:")))
    except (ValueError, AppError):
        await callback.message.answer(texts.CARD_OFF)
        return
    if not plan.price_uzs:
        await callback.message.answer(texts.CARD_OFF)
        return
    assert member is not None
    discount = await premium_service.active_discount(db, member.id)
    price = card_payments.discounted_uzs(plan.price_uzs, discount.percent if discount else None)
    assert price is not None
    if await _instructions(callback.message, db, f"Premium {plan.title}", card_payments.format_uzs(price)):
        await state.set_state(CardReceipt.waiting)
        await state.set_data({"plan_id": plan.id.hex})


@router.callback_query(F.data.startswith("card:stars:"))
async def card_stars(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if not _active(member) or not isinstance(callback.message, Message):
        return
    amount = (callback.data or "").removeprefix("card:stars:")
    package = next((item for item in await card_payments.stars_offer(db) if str(item["stars"]) == amount), None)
    if package is None:
        await callback.message.answer(texts.CARD_OFF)
        return
    what = f"{package['stars']} Telegram Stars"
    if await _instructions(callback.message, db, what, card_payments.format_uzs(package["price_uzs"])):
        await state.set_state(CardReceipt.waiting)
        await state.set_data({"stars": package["stars"]})


@router.callback_query(F.data == "card:don")
async def card_donation(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if not _active(member) or not isinstance(callback.message, Message):
        return
    if await card_payments.card_details(db) is None:
        await callback.message.answer(texts.CARD_OFF)
        return
    await state.set_state(CardDonationAmount.waiting)
    await callback.message.answer(texts.CARD_DONATION_ASK)


@router.message(StateFilter(CardDonationAmount.waiting), F.text, ~F.text.startswith("/"))
async def card_donation_amount(message: Message, state: FSMContext, db: AsyncSession) -> None:
    digits = "".join(char for char in message.text or "" if char.isdigit())
    amount = int(digits) if digits and len(digits) <= 9 else 0
    if amount < card_payments.MIN_DONATION_UZS:
        await message.answer(texts.CARD_DONATION_INVALID)
        return
    if await _instructions(message, db, "Klubga hissa", card_payments.format_uzs(amount)):
        await state.set_state(CardReceipt.waiting)
        await state.set_data({"amount_uzs": amount})


@router.message(StateFilter(CardReceipt.waiting), F.photo | F.document)
async def card_receipt(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if not _active(member) or message.bot is None:
        return
    assert member is not None
    if message.document is not None and not (message.document.mime_type or "").startswith("image/"):
        await message.answer(texts.CARD_RECEIPT_HINT)
        return
    data = await state.get_data()
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id  # type: ignore[union-attr]
    try:
        telegram_file = await message.bot.get_file(file_id)
        assert telegram_file.file_path is not None
        buffer = await message.bot.download_file(telegram_file.file_path)
        await card_payments.submit(
            db,
            member,
            receipt=buffer.read() if buffer else b"",
            plan_id=uuid.UUID(hex=data["plan_id"]) if data.get("plan_id") else None,
            amount_uzs=data.get("amount_uzs"),
            stars=data.get("stars"),
        )
    except AppError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer(texts.CARD_RECEIPT_OK)


@router.message(StateFilter(CardReceipt.waiting), F.text, ~F.text.startswith("/"))
async def card_receipt_hint(message: Message) -> None:
    await message.answer(texts.CARD_RECEIPT_HINT)


# ---------------------------------------------------------------------------- card payments (super admin)


async def _decision_target(callback: CallbackQuery, db: AsyncSession, member: User | None, prefix: str) -> Any:
    if not await access.is_super_admin(db, member):
        await callback.answer(texts.CARD_ADMIN_ONLY, show_alert=True)
        return None
    try:
        return await card_payments.get(db, uuid.UUID(hex=(callback.data or "").removeprefix(prefix)))
    except (ValueError, AppError):
        await callback.answer(texts.FILE_FAILED, show_alert=True)
        return None


async def _describe(db: AsyncSession, payment: Any) -> tuple[str, str, str]:
    user = await db.get(User, payment.user_id)
    plan = await premium_service.get_plan(db, payment.plan_id, active=False) if payment.plan_id else None
    if plan:
        what = f"Premium {plan.title}"
    elif payment.kind == PaymentKind.STARS:
        what = f"{payment.stars} Telegram Stars"
    else:
        what = "Hissa"
    name = f"{user.last_name} {user.first_name}" if user else "—"
    return what, name, card_payments.format_uzs(payment.amount_uzs)


@router.callback_query(F.data.startswith("cp:view:"))
async def card_view(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    payment = await _decision_target(callback, db, member, "cp:view:")
    if payment is None or not isinstance(callback.message, Message):
        return
    await callback.answer()
    what, name, price = await _describe(db, payment)
    caption = texts.CARD_RECEIPT_CAPTION.format(
        what=html.escape(what), price=price, name=html.escape(name), status=payment.status
    )
    image = await card_payments.receipt(db, payment)
    await callback.message.answer_photo(
        BufferedInputFile(image, filename="chek.jpg"),
        caption=caption,
        reply_markup=keyboards.card_decision(payment.id.hex) if payment.status == "PENDING" else None,
    )


@router.callback_query(F.data.startswith("cp:ok:"))
async def card_approve(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    payment = await _decision_target(callback, db, member, "cp:ok:")
    if payment is None:
        return
    assert member is not None
    try:
        await card_payments.approve(db, actor_id=member.id, payment_id=payment.id)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    _, name, price = await _describe(db, payment)
    await callback.answer("✅")
    if not isinstance(callback.message, Message):
        return
    await callback.message.answer(texts.CARD_APPROVED.format(name=html.escape(name), price=price))
    if payment.kind == PaymentKind.STARS:
        user = await db.get(User, payment.user_id)
        assert user is not None
        await callback.message.answer(
            card_payments.gift_steps(payment, user), reply_markup=keyboards.stars_sent(payment.id.hex)
        )


@router.callback_query(F.data.startswith("cp:sent:"))
async def card_stars_sent(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    payment = await _decision_target(callback, db, member, "cp:sent:")
    if payment is None:
        return
    assert member is not None
    try:
        await card_payments.mark_delivered(db, actor_id=member.id, payment_id=payment.id)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    _, name, _ = await _describe(db, payment)
    await callback.answer("⭐")
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.CARD_STARS_DELIVERED.format(name=html.escape(name), stars=payment.stars))


@router.callback_query(F.data.startswith("cp:no:"))
async def card_reject_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    payment = await _decision_target(callback, db, member, "cp:no:")
    if payment is None:
        return
    await callback.answer()
    await state.set_state(CardReject.waiting)
    await state.update_data(payment_id=payment.id.hex)
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.CARD_REJECT_ASK)


@router.message(StateFilter(CardReject.waiting), F.text, ~F.text.startswith("/"))
async def card_reject_reason(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    data = await state.get_data()
    await state.clear()
    if not await access.is_super_admin(db, member) or not data.get("payment_id"):
        await message.answer(texts.CARD_ADMIN_ONLY)
        return
    assert member is not None
    try:
        await card_payments.reject(
            db, actor_id=member.id, payment_id=uuid.UUID(hex=data["payment_id"]), reason=message.text or ""
        )
    except AppError as exc:
        await message.answer(exc.message)
        return
    await message.answer(texts.CARD_REJECTED)
