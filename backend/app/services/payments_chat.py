"""The payments channel («💳 To'lovlar»): everything about money in one place, away from the owners' chats.

When ``payments.chat_id`` is set (a channel or a group where the bot is an administrator), these come
there and nowhere else:

* card receipts with ✅ / ❌ buttons (Premium, Telegram Stars, donations) — see ``card_payments``;
* members' payment questions with «✍️ Javob yozish» — see ``support``;
* every Telegram Stars payment and refund, as a short line;
* a weekly money summary (Mondays);
* a reminder at 10:00 and 17:00 when receipts have waited for hours.

When the chat cannot be reached (the bot was removed), receipts fall back to the super administrators
in the bot, so nothing is ever lost. Adding the bot to a channel as an administrator is enough: the
bot asks the owners in a private message whether that channel is for payments (see the bot's
``chatrole:`` buttons).
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, CardPayment, Payment, PremiumPlan, User
from app.models.enums import CardPaymentStatus, PaymentKind, PaymentStatus
from app.services.audit import record_audit
from app.services.settings import get_setting
from app.utils.timezone import format_datetime, local_tz

logger = logging.getLogger(__name__)
SUMMARY_ACTION = "PAYMENTS_WEEKLY_SUMMARY"
REMINDER_ACTION = "PAYMENTS_PENDING_REMINDER"
REMINDER_HOURS = (10, 17)  # local hours when forgotten receipts are recalled
WAITING_HOURS = 3  # a receipt counts as forgotten after this long


def _e(value: str) -> str:
    return html.escape(value, quote=False)


async def chat_id(session: AsyncSession) -> str | None:
    chat = str(await get_setting(session, "payments.chat_id") or "").strip()
    return chat or None


async def post(session: AsyncSession, text: str, reply_markup: Any = None) -> bool:
    """A message in the payments chat. False when no chat is set or it cannot be reached."""
    from app.services.delivery import optional_bot

    chat = await chat_id(session)
    bot = optional_bot() if chat else None
    if chat is None or bot is None:
        return False
    try:
        await bot.send_message(chat, text, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception:
        logger.warning("The payments chat could not be reached")
        return False
    return True


async def _who(session: AsyncSession, user: User) -> str:
    from app.models import Faculty

    faculty = (
        await session.scalar(select(Faculty.short_name).where(Faculty.id == user.faculty_id))
        if user.faculty_id
        else None
    )
    details = ", ".join(
        part for part in (faculty, f"{user.course}-kurs" if user.course else None, user.group_name) if part
    )
    handle = f" @{user.telegram_username}" if user.telegram_username else ""
    return f"👤 {_e(user.full_name)}{handle}" + (f" · {_e(details)}" if details else "")


async def stars_payment(session: AsyncSession, payment: Payment, user: User) -> bool:
    """A line about a Telegram Stars payment (Premium or a donation)."""
    plan = await session.get(PremiumPlan, payment.plan_id) if payment.plan_id else None
    what = f"💎 Premium «{_e(plan.title)}»" if plan else "💝 Klubga hissa"
    text = (
        f"⭐ <b>Telegram Stars to'lovi</b>\n{await _who(session, user)}\n{what} — <b>{payment.amount} ⭐</b>\n"
        f"🕒 {format_datetime(payment.created_at or datetime.now(UTC))}"
    )
    return await post(session, text)


async def stars_refund(session: AsyncSession, payment: Payment, user: User, actor: User | None) -> bool:
    text = f"↩️ <b>Stars qaytarildi</b>\n{await _who(session, user)}\n{payment.amount} ⭐" + (
        f"\n🛠 {_e(actor.first_name)}" if actor else ""
    )
    return await post(session, text)


async def summary_text(session: AsyncSession, since: datetime, until: datetime) -> str:
    """Money of a period: card payments (UZS) and Telegram Stars, plus what still waits."""
    from app.services.card_payments import format_uzs

    card = (
        await session.execute(
            select(CardPayment.kind, func.count(CardPayment.id), func.coalesce(func.sum(CardPayment.amount_uzs), 0))
            .where(
                CardPayment.status == CardPaymentStatus.APPROVED,
                CardPayment.decided_at >= since,
                CardPayment.decided_at < until,
            )
            .group_by(CardPayment.kind)
        )
    ).all()
    stars = (
        await session.execute(
            select(Payment.kind, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
            .where(
                Payment.status == PaymentStatus.PAID,
                Payment.refunded_at.is_(None),
                Payment.created_at >= since,
                Payment.created_at < until,
            )
            .group_by(Payment.kind)
        )
    ).all()
    waiting = int(
        await session.scalar(select(func.count(CardPayment.id)).where(CardPayment.status == CardPaymentStatus.PENDING))
        or 0
    )
    names = {PaymentKind.PREMIUM: "Premium", PaymentKind.DONATION: "Hissa", PaymentKind.STARS: "Stars (karta)"}
    lines = [
        f"📊 <b>Moliyaviy xulosa</b>: {since.astimezone(local_tz()):%d.%m} — "
        f"{(until - timedelta(seconds=1)).astimezone(local_tz()):%d.%m.%Y}",
        "",
    ]
    if card:
        lines.append("💳 <b>Karta orqali</b> (tasdiqlangan):")
        total = 0
        for kind, count, amount in card:
            lines.append(f"• {names.get(PaymentKind(kind), str(kind))}: {count} ta — {format_uzs(int(amount))}")
            total += int(amount)
        lines.append(f"Jami: <b>{format_uzs(total)}</b>")
    else:
        lines.append("💳 Karta orqali to'lov bo'lmadi.")
    lines.append("")
    if stars:
        lines.append("⭐ <b>Telegram Stars</b>:")
        for kind, count, amount in stars:
            lines.append(f"• {names.get(PaymentKind(kind), str(kind))}: {count} ta — {int(amount)} ⭐")
    else:
        lines.append("⭐ Stars to'lovi bo'lmadi.")
    if waiting:
        lines += ["", f"⏳ Tekshirilmagan cheklar: <b>{waiting}</b>"]
    return "\n".join(lines)


async def weekly_summary(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job (daily at 09:00, acts on Mondays): last week's money in the payments chat."""
    now = now or datetime.now(UTC)
    local = now.astimezone(local_tz())
    if local.weekday() != 0 or await chat_id(session) is None:
        return 0
    until = datetime.combine(local.date(), time.min, tzinfo=local_tz())
    since = until - timedelta(days=7)
    week = until.date().isoformat()
    posted = await session.scalar(
        select(AuditLog.id).where(AuditLog.action == SUMMARY_ACTION, AuditLog.entity_id == week).limit(1)
    )
    if posted is not None:
        return 0  # already posted this week (the job runs several times during that hour)
    if not await post(session, await summary_text(session, since, until)):
        return 0
    record_audit(session, actor_id=None, action=SUMMARY_ACTION, entity_type="payments", entity_id=week)
    await session.commit()
    return 1


async def remind_pending(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: at 10:00 and 17:00, receipts waiting for hours are recalled in the payments chat."""
    now = now or datetime.now(UTC)
    local = now.astimezone(local_tz())
    if local.hour not in REMINDER_HOURS or await chat_id(session) is None:
        return 0
    slot = f"{local.date().isoformat()}-{local.hour}"
    if await session.scalar(
        select(AuditLog.id).where(AuditLog.action == REMINDER_ACTION, AuditLog.entity_id == slot).limit(1)
    ):
        return 0
    count, oldest = (
        await session.execute(
            select(func.count(CardPayment.id), func.min(CardPayment.created_at)).where(
                CardPayment.status == CardPaymentStatus.PENDING,
                CardPayment.created_at < now - timedelta(hours=WAITING_HOURS),
            )
        )
    ).one()
    if not count:
        return 0
    hours = max(WAITING_HOURS, int((now - oldest).total_seconds() // 3600))
    text = (
        f"⏳ <b>Tekshirilmagan cheklar: {count}</b>\n"
        f"Eng eskisi {hours} soatdan beri kutmoqda — a'zolar javob kutyapti. Yuqoridagi cheklarda ✅ yoki ❌ ni "
        "bosing (yoki admin panel → 💎 Premium → Karta to'lovlari)."
    )
    if not await post(session, text):
        return 0
    record_audit(session, actor_id=None, action=REMINDER_ACTION, entity_type="payments", entity_id=slot)
    await session.commit()
    return 1


async def describe(session: AsyncSession) -> dict[str, Any]:
    """For the Admin Panel: which chat is set and whether the bot can write there."""
    from app.services.delivery import optional_bot

    chat = await chat_id(session)
    if chat is None:
        return {"chat_id": None, "title": None, "ok": False, "problem": None}
    bot = optional_bot()
    if bot is None:
        return {"chat_id": chat, "title": None, "ok": False, "problem": "Bot hozir ishlamayapti."}
    try:
        info = await bot.get_chat(chat)
        member = await bot.get_chat_member(info.id, bot.id)
    except Exception:
        return {
            "chat_id": chat,
            "title": None,
            "ok": False,
            "problem": "Kanal topilmadi yoki bot unga qo'shilmagan. Botni kanalga administrator qilib qo'shing.",
        }
    can_post = member.status == "creator" or (
        member.status == "administrator"
        and (info.type != "channel" or bool(getattr(member, "can_post_messages", False)))
    )
    return {
        "chat_id": chat,
        "title": info.title,
        "ok": can_post,
        "problem": None if can_post else "Bot kanalda administrator emas yoki xabar yozish huquqi yo'q.",
    }


async def send_test(session: AsyncSession) -> bool:
    return await post(
        session,
        "✅ <b>Sinov xabari</b>\nBu kanal Kitobxon Hub to'lovlar kanali: cheklar, to'lov savollari va Stars to'lovlari "
        "shu yerga keladi.",
    )
