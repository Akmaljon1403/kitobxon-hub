"""Premium and donations with Telegram Stars, plus /terms and /paysupport (required for payments)."""

from __future__ import annotations

import html
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, texts
from app.bot.states import CardReceipt, CardReject
from app.core.errors import AppError
from app.models import User
from app.models.enums import CardPaymentStatus, FeatureMode, PaymentKind, StickerMood, UserStatus
from app.services import card_payments, features, stickers
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
    """What Premium gives, then how to pay: the bank card first, Telegram Stars second."""
    if await features.mode(db, "premium") == FeatureMode.OFF:
        await message.answer(texts.PREMIUM_CLOSED)
        return
    plans = await premium_service.list_plans(db)
    card = await card_payments.card_details(db) is not None
    await message.answer(
        await _premium_text(db, member),
        reply_markup=keyboards.premium_methods(
            card=card and (any(plan.price_uzs for plan in plans) or bool(await card_payments.stars_offer(db))),
            stars=bool(plans),
            donations=await features.mode(db, "donations") != FeatureMode.OFF or card,
        ),
    )


async def _stars_plans(message: Message, db: AsyncSession, member: User) -> None:
    plans = await premium_service.list_plans(db)
    discount = await premium_service.active_discount(db, member.id)

    def label(plan: Any) -> str:
        if discount is None:
            return texts.PREMIUM_PLAN.format(title=plan.title, stars=plan.stars)
        stars = premium_service.discounted(plan.stars, discount.percent)
        return texts.PREMIUM_PLAN_DISCOUNT.format(title=plan.title, stars=stars, percent=discount.percent)

    await message.answer(
        texts.PREMIUM_STARS_CHOOSE, reply_markup=keyboards.premium_plans([(plan.id.hex, label(plan)) for plan in plans])
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


@router.callback_query(F.data == "prem:stars")
async def premium_stars(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if not _active(member) or not isinstance(callback.message, Message):
        return
    assert member is not None
    if await features.mode(db, "premium") == FeatureMode.OFF:
        await callback.message.answer(texts.PREMIUM_CLOSED)
        return
    await _stars_plans(callback.message, db, member)


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
    """«🤝 Klubni qo'llab-quvvatlash» — open to everyone, entirely optional."""
    await callback.answer()
    if not _active(member) or not isinstance(callback.message, Message):
        return
    stars = await features.mode(db, "donations") != FeatureMode.OFF
    card = await card_payments.card_details(db) is not None
    if not stars and not card:
        await callback.message.answer(texts.DONATE_CLOSED)
        return
    await callback.message.answer(
        texts.DONATE_INFO,
        reply_markup=keyboards.donation_methods(
            card=card, amounts=list(premium_service.DONATION_AMOUNTS) if stars else []
        ),
    )


@router.callback_query(F.data.in_({"don:card", "card:don"}))
async def donate_card(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    """The card number, nothing else: no receipt, no confirmation — a gift is a gift."""
    await callback.answer()
    if not _active(member) or not isinstance(callback.message, Message):
        return
    card = await card_payments.card_details(db)
    if card is None:
        await callback.message.answer(texts.DONATE_CLOSED)
        return
    await state.clear()
    await callback.message.answer(
        texts.DONATE_CARD.format(
            number=html.escape(card["number"]),
            holder=texts.CARD_HOLDER.format(holder=html.escape(card["holder"])) if card["holder"] else "",
        ),
        reply_markup=keyboards.donation_done(),
    )


@router.callback_query(F.data == "don:done")
async def donate_done(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    await callback.answer("💛")
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # an old message
        logger.debug("Donation message could not be edited")
    await callback.message.answer(texts.DONATE_THANKS)
    if member is not None:
        await stickers.send(db, callback.message, StickerMood.CELEBRATE)


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
    buyer = await db.get(User, stored.user_id)
    if buyer is not None:
        from app.services import payments_chat

        await payments_chat.stars_payment(db, stored, buyer)  # a line in the payments channel


@router.message(Command("terms"))
async def terms(message: Message) -> None:
    await message.answer(texts.TERMS)


@router.message(Command("paysupport"))
async def paysupport(message: Message, member: User | None) -> None:
    markup = (
        keyboards.inline([InlineKeyboardButton(text=texts.BTN_WRITE_PAYMENT, callback_data="sup:new:pay")])
        if _active(member)
        else None
    )
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
    if not _active(member) or not isinstance(callback.message, Message):
        await callback.answer()
        return
    assert member is not None
    if member.telegram_username != callback.from_user.username:
        member.telegram_username = callback.from_user.username  # renamed in Telegram since the last visit
        await db.commit()
    if not member.telegram_username:
        await callback.answer()
        await callback.message.answer(card_payments.STARS_NEED_USERNAME)
        return
    await callback.answer()
    amount = (callback.data or "").removeprefix("card:stars:")
    package = next((item for item in await card_payments.stars_offer(db) if str(item["stars"]) == amount), None)
    if package is None:
        await callback.message.answer(texts.CARD_OFF)
        return
    what = f"{package['stars']} Telegram Stars"
    if await _instructions(callback.message, db, what, card_payments.format_uzs(package["price_uzs"])):
        await state.set_state(CardReceipt.waiting)
        await state.set_data({"stars": package["stars"]})


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
# The receipts come to the payments chat (a group or a channel) or to the super admins in the bot.
# Decisions edit that message: a line saying who decided and when, and «↩️ Qaytarish» for mistakes.


async def _decision_target(callback: CallbackQuery, db: AsyncSession, member: User | None, prefix: str) -> Any:
    if not await access.is_super_admin(db, member):
        await callback.answer(texts.CARD_ADMIN_ONLY, show_alert=True)
        return None
    try:
        return await card_payments.get(db, uuid.UUID(hex=(callback.data or "").removeprefix(prefix)[:32]))
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


def _now_text() -> str:
    from app.utils.timezone import format_datetime

    return format_datetime(datetime.now(UTC))


async def _show_decision(callback: CallbackQuery, payment: Any, line: str, markup: Any) -> None:
    """Add «who decided, when» to the receipt message and change its buttons."""
    message = callback.message
    if not isinstance(message, Message):
        return
    base = message.html_text or ""
    text = f"{base}\n\n{line}"
    try:
        if message.photo or message.document:
            if len(text) > 1000:
                raise ValueError("caption too long")
            await message.edit_caption(caption=text, reply_markup=markup)
        else:
            await message.edit_text(text, reply_markup=markup)
    except Exception:  # too old or too long to edit: say it in a new message
        await message.answer(line, reply_markup=markup)


def _decided_markup(payment: Any) -> Any:
    stars_to_send = (
        payment.kind == PaymentKind.STARS
        and payment.status == CardPaymentStatus.APPROVED
        and payment.delivered_at is None
    )
    return keyboards.card_decided(payment.id.hex, stars_to_send=stars_to_send)


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
    pending = payment.status == CardPaymentStatus.PENDING
    await callback.message.answer_photo(
        BufferedInputFile(image, filename="chek.jpg"),
        caption=caption,
        reply_markup=keyboards.card_decision(payment.id.hex) if pending else _decided_markup(payment),
    )


@router.callback_query(F.data.startswith("cp:ok:"))
async def card_approve(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    payment = await _decision_target(callback, db, member, "cp:ok:")
    if payment is None:
        return
    assert member is not None
    try:
        payment = await card_payments.approve(db, actor_id=member.id, payment_id=payment.id)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await callback.answer("✅")
    line = texts.CARD_LINE_APPROVED.format(admin=html.escape(member.first_name), time=_now_text())
    await _show_decision(callback, payment, line, _decided_markup(payment))
    if payment.kind == PaymentKind.STARS and isinstance(callback.message, Message):
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
        payment = await card_payments.mark_delivered(db, actor_id=member.id, payment_id=payment.id)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await callback.answer("⭐")
    line = texts.CARD_LINE_SENT.format(admin=html.escape(member.first_name), time=_now_text())
    await _show_decision(callback, payment, line, None)


@router.callback_query(F.data.startswith("cp:no:"))
async def card_reject_start(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    """Quick reasons as buttons (they work in a group or a channel too), or «✍️ Boshqa sabab»."""
    payment = await _decision_target(callback, db, member, "cp:no:")
    if payment is None:
        return
    await callback.answer(texts.CARD_REJECT_PICK)
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboards.card_reject_reasons(payment.id.hex))
        except Exception:
            await callback.message.answer(
                texts.CARD_REJECT_PICK, reply_markup=keyboards.card_reject_reasons(payment.id.hex)
            )


@router.callback_query(F.data.startswith("cp:back:"))
async def card_reject_back(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    payment = await _decision_target(callback, db, member, "cp:back:")
    if payment is None:
        return
    await callback.answer()
    if isinstance(callback.message, Message):
        view = not (callback.message.photo or callback.message.document)
        await callback.message.edit_reply_markup(reply_markup=keyboards.card_decision(payment.id.hex, view=view))


async def _reject(callback: CallbackQuery, db: AsyncSession, member: User, payment: Any, reason: str) -> None:
    try:
        payment = await card_payments.reject(db, actor_id=member.id, payment_id=payment.id, reason=reason)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await callback.answer("❌")
    line = texts.CARD_LINE_REJECTED.format(
        admin=html.escape(member.first_name), time=_now_text(), reason=html.escape(reason)
    )
    await _show_decision(callback, payment, line, _decided_markup(payment))


@router.callback_query(F.data.startswith("cp:nr:"))
async def card_reject_reason_button(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    payment = await _decision_target(callback, db, member, "cp:nr:")
    if payment is None:
        return
    assert member is not None
    try:
        reason = texts.CARD_REJECT_REASONS[int((callback.data or "").rsplit(":", 1)[1])]
    except (ValueError, IndexError):
        await callback.answer()
        return
    await _reject(callback, db, member, payment, reason)


@router.callback_query(F.data.startswith("cp:nw:"))
async def card_reject_typed(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    """The admin types the reason in their private chat with the bot (that works from a channel, too)."""
    payment = await _decision_target(callback, db, member, "cp:nw:")
    if payment is None or callback.bot is None:
        return
    what, name, _ = await _describe(db, payment)
    private = state
    if not isinstance(callback.message, Message) or callback.message.chat.type != "private":
        private = FSMContext(
            storage=state.storage,
            key=StorageKey(bot_id=callback.bot.id, chat_id=callback.from_user.id, user_id=callback.from_user.id),
        )
    try:
        await callback.bot.send_message(
            callback.from_user.id, texts.CARD_REJECT_ASK_PRIVATE.format(what=html.escape(what), name=html.escape(name))
        )
    except Exception:
        await callback.answer(texts.CARD_DM_FIRST, show_alert=True)
        return
    await private.set_state(CardReject.waiting)
    origin = callback.message if isinstance(callback.message, Message) else None
    await private.update_data(
        payment_id=payment.id.hex,
        # The receipt in the payments channel gets the decision line once the reason is typed.
        origin_chat=origin.chat.id if origin else None,
        origin_message=origin.message_id if origin else None,
        origin_text=(origin.html_text or "") if origin else "",
        origin_media=bool(origin and (origin.photo or origin.document)),
    )
    await callback.answer("✍️")


async def _mark_origin(bot: Any, data: dict[str, Any], payment: Any, line: str) -> None:
    """After a typed reason: the receipt message (in the channel or the chat) shows who decided, and why."""
    chat, message_id = data.get("origin_chat"), data.get("origin_message")
    if chat is None or message_id is None or bot is None:
        return
    text = f"{data.get('origin_text') or ''}\n\n{line}"
    markup = _decided_markup(payment)
    try:
        if data.get("origin_media"):
            if len(text) > 1000:
                raise ValueError("caption too long")
            await bot.edit_message_caption(chat_id=chat, message_id=message_id, caption=text, reply_markup=markup)
        else:
            await bot.edit_message_text(text, chat_id=chat, message_id=message_id, reply_markup=markup)
    except Exception:
        try:
            await bot.send_message(chat, line, reply_markup=markup, reply_to_message_id=message_id)
        except Exception:
            logger.warning("The receipt message could not be updated after a typed reason")


@router.message(StateFilter(CardReject.waiting), F.text, ~F.text.startswith("/"))
async def card_reject_reason(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    data = await state.get_data()
    await state.clear()
    if not await access.is_super_admin(db, member) or not data.get("payment_id"):
        await message.answer(texts.CARD_ADMIN_ONLY)
        return
    assert member is not None
    try:
        payment = await card_payments.reject(
            db, actor_id=member.id, payment_id=uuid.UUID(hex=data["payment_id"]), reason=message.text or ""
        )
    except AppError as exc:
        await message.answer(exc.message)
        return
    await message.answer(texts.CARD_REJECTED)
    line = texts.CARD_LINE_REJECTED.format(
        admin=html.escape(member.first_name), time=_now_text(), reason=html.escape(payment.reject_reason or "")
    )
    await _mark_origin(message.bot, data, payment, line)


@router.callback_query(F.data.startswith("cp:undo:"))
async def card_undo(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    payment = await _decision_target(callback, db, member, "cp:undo:")
    if payment is None:
        return
    assert member is not None
    try:
        payment = await card_payments.undo(db, actor_id=member.id, payment_id=payment.id)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await callback.answer("↩️")
    line = texts.CARD_LINE_UNDONE.format(admin=html.escape(member.first_name), time=_now_text())
    view = isinstance(callback.message, Message) and not (callback.message.photo or callback.message.document)
    await _show_decision(callback, payment, line, keyboards.card_decision(payment.id.hex, view=view))
