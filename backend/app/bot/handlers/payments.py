"""Premium and donations with Telegram Stars, plus /terms and /paysupport (required for payments)."""

from __future__ import annotations

import html
import logging
import uuid

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts
from app.core.errors import AppError
from app.models import User
from app.models.enums import FeatureMode, PaymentKind, UserStatus
from app.services import features
from app.services import premium as premium_service
from app.utils.timezone import format_date

logger = logging.getLogger(__name__)
router = Router(name="payments")


def _active(member: User | None) -> bool:
    return member is not None and member.status == UserStatus.ACTIVE


async def _premium_text(db: AsyncSession, member: User) -> str:
    status = await premium_service.member_status(db, member)
    current = (
        texts.PREMIUM_STATUS_ON.format(until=format_date(status["until"]))
        if status["is_premium"] and status["until"]
        else texts.PREMIUM_STATUS_OFF
    )
    perks = [
        texts.PREMIUM_PERK.format(title=f["title"], description=f["description"]) for f in status["premium_features"]
    ]
    perks.append(texts.PREMIUM_PERK_GOLD)
    return texts.PREMIUM_INFO.format(status=current, perks="\n".join(perks))


async def show_premium(message: Message, db: AsyncSession, member: User) -> None:
    if await features.mode(db, "premium") == FeatureMode.OFF:
        await message.answer(texts.PREMIUM_CLOSED)
        return
    plans = await premium_service.list_plans(db)
    donations = await features.mode(db, "donations") != FeatureMode.OFF
    await message.answer(
        await _premium_text(db, member),
        reply_markup=keyboards.premium_plans(
            [(plan.id.hex, texts.PREMIUM_PLAN.format(title=plan.title, stars=plan.stars)) for plan in plans],
            donations=donations,
        ),
    )


@router.message(Command("premium"))
async def premium_command(message: Message, db: AsyncSession, member: User | None) -> None:
    if not _active(member):
        await message.answer(texts.NOT_REGISTERED)
        return
    assert member is not None
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
    await callback.bot.send_invoice(chat_id=callback.message.chat.id, **premium_service.plan_invoice(plan, member))


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
