"""Members' messages to the club administrators and the administrators' answers.

Members write through the bot. Every administrator who may answer (``SUPPORT_MANAGE``; for money
questions the super admins and ``PAYMENT_SUPPORT``) gets the whole message with «✍️ Javob yozish» and
«📄 Batafsil»; they answer in the bot, in the payments channel (a «Reply») or in the Admin Panel. Every
copy shows the state — «⏳ Javob kutmoqda», «✍️ … javob yozmoqda», «✅ Javob berildi — who, when, what» —
the same for all admins (``copies.settle``). Answers reach the member signed by "Klub rahbariyati" —
never with the administrator's name or account.
"""

from __future__ import annotations

import html
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError, RateLimitedError
from app.models import Faculty, SupportMessage, SupportTicket, User
from app.models.enums import NotificationType, SupportTicketStatus
from app.security.permissions import Perm
from app.services import copies
from app.services.audit import record_audit
from app.services.notifications import enqueue_for_members, enqueue_notification

MAX_TEXT = 3000
# A member may send at most this many messages per hour (protects admins from floods).
HOURLY_LIMIT = 10
PREVIEW = 300

logger = logging.getLogger(__name__)


def _clean(text: str | None) -> str:
    value = (text or "").strip()
    if len(value) > MAX_TEXT:
        value = value[:MAX_TEXT]
    return value


async def _open_ticket(session: AsyncSession, user_id: uuid.UUID) -> SupportTicket:
    ticket = await session.scalar(
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id, SupportTicket.status != SupportTicketStatus.CLOSED)
        .order_by(SupportTicket.created_at.desc())
        .limit(1)
    )
    if ticket is None:
        ticket = SupportTicket(user_id=user_id)
        session.add(ticket)
        await session.flush()
    return ticket


async def member_message(
    session: AsyncSession,
    *,
    user: User,
    text: str | None,
    photo_file_id: str | None = None,
    topic: str | None = None,
) -> SupportTicket:
    """Store a member's message and tell the administrators (a payment question also goes to the
    payments chat). The caller commits."""
    body = _clean(text)
    if not body and not photo_file_id:
        raise BadRequestError("SUPPORT_EMPTY", "Xabar bo'sh. Savolingizni matn ko'rinishida yozing.")
    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    recent = await session.scalar(
        select(func.count())
        .select_from(SupportMessage)
        .join(SupportTicket, SupportTicket.id == SupportMessage.ticket_id)
        .where(
            SupportTicket.user_id == user.id,
            SupportMessage.from_admin.is_(False),
            SupportMessage.created_at >= hour_ago,
        )
    )
    if (recent or 0) >= HOURLY_LIMIT:
        raise RateLimitedError(
            "SUPPORT_TOO_MANY", "Juda ko'p xabar yubordingiz. Javobni kuting yoki bir soatdan so'ng yozing."
        )
    ticket = await _open_ticket(session, user.id)
    now = datetime.now(UTC)
    message = SupportMessage(ticket_id=ticket.id, text=body or "📷 (rasm)", photo_file_id=photo_file_id)
    session.add(message)
    ticket.status = SupportTicketStatus.OPEN
    ticket.unread_for_admin = True
    ticket.last_message_at = now
    await session.flush()

    faculty = (
        await session.scalar(select(Faculty.name).where(Faculty.id == user.faculty_id)) if user.faculty_id else None
    )
    who = html.escape(user.full_name, quote=False)
    if user.telegram_username:
        who += f" (@{html.escape(user.telegram_username)})"
    details = ", ".join(
        part
        for part in (
            html.escape(faculty, quote=False) if faculty else None,
            f"{user.course}-kurs" if user.course else None,
            f"{html.escape(user.group_name, quote=False)}-guruh" if user.group_name else None,
        )
        if part
    )
    waiting = await session.scalar(
        select(func.count())
        .select_from(SupportMessage)
        .where(
            SupportMessage.ticket_id == ticket.id,
            SupportMessage.from_admin.is_(False),
            SupportMessage.created_at > _last_answer_at(ticket.id),
        )
    )
    title = "💳 <b>To'lov bo'yicha murojaat</b>" if topic == "payment" else "📨 <b>Yangi murojaat</b>"
    if (waiting or 0) > 1:
        title += f" <i>({waiting}-xabar, javob kutilmoqda)</i>"
    # The whole message (up to 3000 characters fits Telegram's 4096); «📄 Batafsil» shows the conversation.
    body_html = html.escape(body, quote=False) if body else ""
    if photo_file_id:
        body_html = (body_html + "\n\n" if body_html else "") + "📷 <i>Rasm ilova qilingan — «📄 Batafsil»</i>"
    base = f"{title}\n👤 {who}" + (f"\n🎓 {details}" if details else "") + f"\n\n{body_html}"
    sync = f"ticket:{ticket.id}"
    if topic == "payment":
        # Money questions are a conversation between the member and the super admins (and the admins given
        # «💳 To'lov savollari»): they live in the payments chat, or come to them in the bot without one.
        if not await _to_payments_chat(session, base, ticket):
            from app.services.rbac import admins_with_permission

            await enqueue_for_members(
                session,
                type_=NotificationType.SUPPORT,
                text=copies.compose(base, WAITING),
                dedup_prefix=f"support:{message.id}",
                members=admins_with_permission(Perm.PAYMENT_SUPPORT),
                payload={"base": base, "buttons": waiting_buttons(ticket.id, payment=True)},
                priority=1,
                sync=sync,
            )
        return ticket
    from app.services.rbac import admins_with_permission

    await enqueue_for_members(
        session,
        type_=NotificationType.SUPPORT,
        text=copies.compose(base, WAITING),
        dedup_prefix=f"support:{message.id}",
        members=admins_with_permission(Perm.SUPPORT_MANAGE),
        payload={"base": base, "buttons": waiting_buttons(ticket.id, payment=False)},
        priority=2,
        sync=sync,
    )
    return ticket


WAITING = "⏳ <b>Holat:</b> javob kutmoqda"
PAY_HINT = "\n\n<i>↩️ Javob berish: shu xabarga «Reply» qilib yozing (yoki «✍️ Javob yozish»).</i>"


def _last_answer_at(ticket_id: uuid.UUID) -> Any:
    """When the club last wrote in this conversation (the start of time when never)."""
    return (
        select(func.coalesce(func.max(SupportMessage.created_at), datetime(2000, 1, 1, tzinfo=UTC)))
        .where(SupportMessage.ticket_id == ticket_id, SupportMessage.from_admin.is_(True))
        .scalar_subquery()
    )


def waiting_buttons(ticket_id: uuid.UUID, *, payment: bool, answered: bool = False) -> list[dict[str, Any]]:
    """The buttons under every copy: answer, the whole conversation, the panel, close."""
    answer = {"text": "✍️ Yana yozish" if answered else "✍️ Javob yozish", "callback": _answer_cb(ticket_id, payment)}
    full = {"text": "📄 Batafsil", "callback": _full_cb(ticket_id, payment)}
    rows: list[dict[str, Any]] = [{"row": [answer, full]}]
    if not payment:
        rows.append({"text": "🛠 Admin panelda ochish", "admin_route": f"support/{ticket_id}"})
    rows.append({"text": "🔒 Yopish", "callback": f"sup:close:{ticket_id}"})
    return rows


def _answer_cb(ticket_id: uuid.UUID, payment: bool) -> str:
    return f"{'sup:pay:' if payment else 'sup:ans:'}{ticket_id}"


def _full_cb(ticket_id: uuid.UUID, payment: bool) -> str:
    return f"{'sup:full:p:' if payment else 'sup:full:'}{ticket_id}"


def payments_markup(ticket_id: uuid.UUID, *, answered: bool = False) -> Any:
    """The buttons of a payment question in the payments chat."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Yana yozish" if answered else "✍️ Javob yozish", callback_data=_answer_cb(ticket_id, True)
                ),
                InlineKeyboardButton(text="📄 Batafsil", callback_data=_full_cb(ticket_id, True)),
            ]
        ]
    )


async def _is_payment(session: AsyncSession, ticket_id: uuid.UUID) -> bool:
    """Was this conversation about money (its questions went to the payments chat or its people)?"""
    from app.models import PaymentsChatLink

    linked = await session.scalar(
        select(PaymentsChatLink.message_id)
        .where(PaymentsChatLink.kind == "ticket", PaymentsChatLink.target_id == ticket_id)
        .limit(1)
    )
    if linked is not None:
        return True
    from app.models import Notification

    first = await session.scalar(
        select(Notification.payload)
        .where(Notification.sync_key == f"ticket:{ticket_id}")
        .order_by(Notification.created_at)
        .limit(1)
    )
    return bool(first and any("sup:pay:" in str(button) for button in first.get("buttons", [])))


async def settle_ticket(
    session: AsyncSession, ticket_id: uuid.UUID, status: str, *, answered: bool, closed: bool = False
) -> None:
    """Show the conversation's state under every admin's copy and in the payments chat."""
    payment = await _is_payment(session, ticket_id)
    if closed:
        buttons: list[dict[str, Any]] = [{"text": "📄 Batafsil", "callback": _full_cb(ticket_id, payment)}]
    else:
        buttons = waiting_buttons(ticket_id, payment=payment, answered=answered)
    await copies.settle(
        session,
        f"ticket:{ticket_id}",
        status,
        buttons=buttons,
        payments_buttons=payments_markup(ticket_id, answered=answered),
    )


async def member_thread(session: AsyncSession, user_id: uuid.UUID, limit: int = 50) -> list[SupportMessage]:
    """The member's conversation with the club (newest last), for the Mini App."""
    rows = list(
        await session.scalars(
            select(SupportMessage)
            .join(SupportTicket, SupportTicket.id == SupportMessage.ticket_id)
            .where(SupportTicket.user_id == user_id)
            .order_by(SupportMessage.created_at.desc())
            .limit(limit)
        )
    )
    return list(reversed(rows))


async def _to_payments_chat(session: AsyncSession, base: str, ticket: SupportTicket) -> bool:
    """A payment question in the payments chat, with «✍️ Javob yozish» and «📄 Batafsil» — or answered right
    there by replying to it. False when it could not go there."""
    from app.services import payments_chat

    text = base + PAY_HINT
    return await payments_chat.post(
        session,
        copies.compose(text, WAITING),
        payments_markup(ticket.id),
        link=("ticket", ticket.id, ticket.user_id),
        base_text=text,
    )


async def admin_reply(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    ticket_id: uuid.UUID,
    text: str,
    payment: bool = False,
    echo: bool = True,
    signature: str | None = None,
) -> SupportMessage:
    """``payment``: an answer to a money question — the member continues in the same topic, and the
    answer is written in the payments chat too (``echo=False``: it was written there already, as a reply).
    ``actor_id`` is None for an answer posted in the payments channel by an admin we cannot name
    (``signature``: the channel's «signed by» name, when it signs posts)."""
    body = _clean(text)
    if not body:
        raise BadRequestError("SUPPORT_EMPTY", "Javob matnini yozing.")
    ticket = await get_ticket(session, ticket_id)
    message = SupportMessage(ticket_id=ticket.id, from_admin=True, admin_id=actor_id, text=body)
    session.add(message)
    ticket.status = SupportTicketStatus.ANSWERED
    ticket.unread_for_admin = False
    ticket.last_message_at = datetime.now(UTC)
    await session.flush()
    await enqueue_notification(
        session,
        user_id=ticket.user_id,
        type_=NotificationType.SUPPORT,
        text=f"📩 <b>Klub rahbariyatidan javob</b>\n\n{html.escape(body, quote=False)}",
        dedup_key=f"support-reply:{message.id}",
        # A blocked member gets the answer too: writing to the club is how they sort it out.
        payload={
            "buttons": [{"text": "✍️ Yana yozish", "callback": "sup:new:pay" if payment else "sup:new"}],
            "deliver_to_inactive": True,
        },
        priority=1,
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="SUPPORT_REPLY",
        entity_type="support_ticket",
        entity_id=ticket.id,
        after={"length": len(body), **({"signature": signature} if signature else {})},
    )
    who = await copies.admin_name(session, actor_id) if actor_id else html.escape(signature or "kanal orqali")
    preview = body if len(body) <= 300 else body[:300] + "…"
    status = f"✅ <b>Javob berildi</b> — {who}, {copies.stamp()}\n💬 <i>{html.escape(preview, quote=False)}</i>"
    await settle_ticket(session, ticket.id, status, answered=True)
    await session.commit()
    if payment and echo:
        from app.services import payments_chat

        member = await session.get(User, ticket.user_id)
        await payments_chat.post(
            session,
            f"↪️ <b>Javob</b> — {who} → {html.escape(member.full_name if member else '—', quote=False)}\n\n"
            f"{html.escape(body, quote=False)}",
            link=("ticket", ticket.id, ticket.user_id),
        )
    return message


async def claim(
    session: AsyncSession, *, actor_id: uuid.UUID, ticket_id: uuid.UUID, chat_id: int, message_id: int
) -> None:
    """«✍️ Javob yozish» pressed in the payments channel: this admin answers (their «Reply» there is theirs),
    and everybody sees who took it."""
    from app.models import PaymentsChatLink

    link = await session.get(PaymentsChatLink, (chat_id, message_id))
    if link is not None:
        link.claimed_by = actor_id
        link.claimed_at = datetime.now(UTC)
    ticket = await get_ticket(session, ticket_id)
    if ticket.status != SupportTicketStatus.CLOSED:
        status = f"✍️ <b>{await copies.admin_name(session, actor_id)}</b> javob yozmoqda… ({copies.stamp()})"
        await settle_ticket(session, ticket.id, status, answered=ticket.status == SupportTicketStatus.ANSWERED)
    await session.commit()


CLAIM_VALID = timedelta(minutes=30)


async def claimer(session: AsyncSession, chat_id: int, message_id: int, ticket_id: uuid.UUID) -> uuid.UUID | None:
    """Who pressed «✍️ Javob yozish» on this question in the last half hour (their reply is theirs)."""
    from app.models import PaymentsChatLink

    recent = datetime.now(UTC) - CLAIM_VALID
    link = await session.get(PaymentsChatLink, (chat_id, message_id))
    if link is not None and link.claimed_by and link.claimed_at and link.claimed_at >= recent:
        return link.claimed_by
    return await session.scalar(
        select(PaymentsChatLink.claimed_by)
        .where(
            PaymentsChatLink.kind == "ticket",
            PaymentsChatLink.target_id == ticket_id,
            PaymentsChatLink.claimed_at >= recent,
        )
        .order_by(PaymentsChatLink.claimed_at.desc())
        .limit(1)
    )


async def thread_text(session: AsyncSession, ticket_id: uuid.UUID, limit: int = 20) -> tuple[list[str], list[str]]:
    """«📄 Batafsil»: the conversation for the admins, as Telegram messages (each under 4096 characters),
    and the members' photos (file ids) to send after it."""
    ticket = await get_ticket(session, ticket_id)
    user = await session.get(User, ticket.user_id)
    rows = (
        await session.execute(
            select(SupportMessage, User.first_name, User.last_name)
            .outerjoin(User, User.id == SupportMessage.admin_id)
            .where(SupportMessage.ticket_id == ticket.id)
            .order_by(SupportMessage.created_at.desc())
            .limit(limit)
        )
    ).all()
    states = {
        SupportTicketStatus.OPEN: "⏳ javob kutmoqda",
        SupportTicketStatus.ANSWERED: "✅ javob berilgan",
        SupportTicketStatus.CLOSED: "🔒 yopilgan",
    }
    head = (
        f"📄 <b>Murojaat to'liq</b> — {html.escape(user.full_name if user else '—', quote=False)}\n"
        f"Holat: {states.get(ticket.status, '—')} · xabarlar: {len(rows)}"
        + (f" (oxirgi {limit} tasi)" if len(rows) == limit else "")
    )
    parts: list[str] = []
    photos: list[str] = []
    for message, first, last in reversed(rows):
        when = copies.stamp(message.created_at)
        if message.from_admin:
            name = html.escape(f"{first} {last or ''}".strip(), quote=False) if first else "Klub"
            parts.append(f"🛡 <b>{name}</b> · {when}\n{html.escape(message.text, quote=False)}")
        else:
            parts.append(f"👤 <b>A'zo</b> · {when}\n{html.escape(message.text, quote=False)}")
            if message.photo_file_id:
                photos.append(message.photo_file_id)
    chunks: list[str] = []
    current = head
    for part in parts:
        if len(current) + len(part) + 2 > 4000:
            chunks.append(current)
            current = part
        else:
            current = f"{current}\n\n{part}"
    chunks.append(current)
    return chunks, photos


async def club_message(
    session: AsyncSession, *, actor_id: uuid.UUID | None, user_id: uuid.UUID, text: str, about: str
) -> SupportMessage:
    """The club writes to a member first about money (a reply in the payments channel to a receipt or a
    Stars payment): it goes into the member's conversation, and they can answer with one tap."""
    body = _clean(text)
    if not body:
        raise BadRequestError("SUPPORT_EMPTY", "Xabar matnini yozing.")
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None or user.erased_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "A'zo topilmadi.")
    ticket = await _open_ticket(session, user_id)
    message = SupportMessage(ticket_id=ticket.id, from_admin=True, admin_id=actor_id, text=body)
    session.add(message)
    ticket.status = SupportTicketStatus.ANSWERED
    ticket.last_message_at = datetime.now(UTC)
    await session.flush()
    await enqueue_notification(
        session,
        user_id=user_id,
        type_=NotificationType.SUPPORT,
        text=(
            f"📩 <b>Klub rahbariyatidan</b> — <i>{html.escape(about, quote=False)}</i>\n\n"
            f"{html.escape(body, quote=False)}"
        ),
        dedup_key=f"support-reply:{message.id}",
        payload={"buttons": [{"text": "✍️ Javob yozish", "callback": "sup:new:pay"}], "deliver_to_inactive": True},
        priority=1,
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="SUPPORT_CLUB_MESSAGE",
        entity_type="support_ticket",
        entity_id=ticket.id,
        after={"length": len(body), "about": about},
    )
    await session.commit()
    return message


async def get_ticket(session: AsyncSession, ticket_id: uuid.UUID) -> SupportTicket:
    ticket = await session.get(SupportTicket, ticket_id)
    if ticket is None:
        raise NotFoundError("TICKET_NOT_FOUND", "Murojaat topilmadi.")
    return ticket


async def set_status(
    session: AsyncSession, *, actor_id: uuid.UUID, ticket_id: uuid.UUID, status: SupportTicketStatus
) -> SupportTicket:
    ticket = await get_ticket(session, ticket_id)
    before = ticket.status
    ticket.status = status
    if status == SupportTicketStatus.CLOSED:
        ticket.unread_for_admin = False
    if status != before:
        who = await copies.admin_name(session, actor_id)
        if status == SupportTicketStatus.CLOSED:
            await settle_ticket(
                session, ticket.id, f"🔒 <b>Yopildi</b> — {who}, {copies.stamp()}", answered=True, closed=True
            )
        elif status == SupportTicketStatus.OPEN:
            await settle_ticket(session, ticket.id, f"{WAITING} <i>(qayta ochdi: {who})</i>", answered=False)
    record_audit(
        session,
        actor_id=actor_id,
        action="SUPPORT_STATUS",
        entity_type="support_ticket",
        entity_id=ticket.id,
        before={"status": before},
        after={"status": status},
    )
    await session.commit()
    return ticket


async def list_tickets(
    session: AsyncSession, *, status: SupportTicketStatus | None, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    conditions = [SupportTicket.status == status] if status else []
    total = await session.scalar(select(func.count()).select_from(SupportTicket).where(*conditions))
    last_text = (
        select(SupportMessage.text)
        .where(SupportMessage.ticket_id == SupportTicket.id)
        .order_by(SupportMessage.created_at.desc())
        .limit(1)
        .correlate(SupportTicket)
        .scalar_subquery()
    )
    count = (
        select(func.count())
        .where(SupportMessage.ticket_id == SupportTicket.id)
        .correlate(SupportTicket)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(SupportTicket, User, Faculty.name, last_text, count)
        .join(User, User.id == SupportTicket.user_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .where(*conditions)
        .order_by(SupportTicket.unread_for_admin.desc(), SupportTicket.last_message_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        {
            "id": ticket.id,
            "status": ticket.status,
            "unread": ticket.unread_for_admin,
            "last_message_at": ticket.last_message_at,
            "created_at": ticket.created_at,
            "last_text": (text or "")[:PREVIEW],
            "message_count": int(messages or 0),
            "member": _member(user, faculty),
        }
        for ticket, user, faculty, text, messages in rows
    ]
    return items, int(total or 0)


def _member(user: User, faculty: str | None) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "faculty": faculty,
        "course": user.course,
        "group_name": user.group_name,
        "telegram_username": user.telegram_username,
    }


async def ticket_detail(session: AsyncSession, ticket_id: uuid.UUID, *, mark_read: bool = True) -> dict[str, Any]:
    ticket = await get_ticket(session, ticket_id)
    user = await session.get(User, ticket.user_id)
    assert user is not None
    faculty = (
        await session.scalar(select(Faculty.name).where(Faculty.id == user.faculty_id)) if user.faculty_id else None
    )
    rows = await session.execute(
        select(SupportMessage, User.first_name, User.last_name)
        .outerjoin(User, User.id == SupportMessage.admin_id)
        .where(SupportMessage.ticket_id == ticket.id)
        .order_by(SupportMessage.created_at)
    )
    messages = [
        {
            "id": message.id,
            "from_admin": message.from_admin,
            "admin_name": f"{first} {last}" if message.from_admin and first else None,
            "text": message.text,
            "has_photo": message.photo_file_id is not None,
            "created_at": message.created_at,
        }
        for message, first, last in rows
    ]
    if mark_read and ticket.unread_for_admin:
        ticket.unread_for_admin = False
        await session.commit()
    return {
        "id": ticket.id,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "member": _member(user, faculty),
        "messages": messages,
    }


async def unread_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(SupportTicket).where(SupportTicket.unread_for_admin.is_(True))
        )
        or 0
    )


async def photo_file_id(session: AsyncSession, message_id: uuid.UUID) -> str:
    file_id = await session.scalar(select(SupportMessage.photo_file_id).where(SupportMessage.id == message_id))
    if not file_id:
        raise NotFoundError("PHOTO_NOT_FOUND", "Rasm topilmadi.")
    return file_id
