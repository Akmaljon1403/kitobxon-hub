"""Members' messages to the club administrators and the administrators' answers.

Members write through the bot. Every administrator who may answer (``SUPPORT_MANAGE``) gets a
Telegram message with a reply button; they answer in the bot or in the Admin Panel. Answers reach
the member signed by "Klub rahbariyati" — never with the administrator's name or account.
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

    from app.services.rbac import admins_with_permission

    faculty = (
        await session.scalar(select(Faculty.name).where(Faculty.id == user.faculty_id)) if user.faculty_id else None
    )
    who = html.escape(user.full_name)
    details = ", ".join(
        part
        for part in (
            html.escape(faculty) if faculty else None,
            f"{user.course}-kurs" if user.course else None,
            html.escape(user.group_name) if user.group_name else None,
        )
        if part
    )
    preview = html.escape(body[:PREVIEW] + ("…" if len(body) > PREVIEW else "")) if body else "📷 Rasm yubordi"
    title = "💳 <b>To'lov bo'yicha murojaat</b>" if topic == "payment" else "📨 <b>Yangi murojaat</b>"
    text = f"{title}\n👤 {who}" + (f" · {details}" if details else "") + f"\n\n{preview}"
    if topic == "payment":
        # Money questions are a conversation between the member and the super admins: they live in the
        # payments chat (or, without one, come to the super admins in the bot).
        if not await _to_payments_chat(session, text, ticket):
            from app.services.rbac import super_admins

            await enqueue_for_members(
                session,
                type_=NotificationType.SUPPORT,
                text=text,
                dedup_prefix=f"support:{message.id}",
                members=super_admins(),
                payload={"buttons": [{"text": "✍️ Javob yozish", "callback": f"sup:pay:{ticket.id}"}]},
                priority=1,
            )
        return ticket
    await enqueue_for_members(
        session,
        type_=NotificationType.SUPPORT,
        text=text,
        dedup_prefix=f"support:{message.id}",
        members=admins_with_permission(Perm.SUPPORT_MANAGE),
        payload={
            "buttons": [
                {"text": "✍️ Javob yozish", "callback": f"sup:ans:{ticket.id}"},
                {"text": "🛠 Admin panelda ochish", "admin_route": f"support/{ticket.id}"},
            ]
        },
        priority=2,
    )
    return ticket


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


async def _to_payments_chat(session: AsyncSession, text: str, ticket: SupportTicket) -> bool:
    """A payment question in the payments chat, with «✍️ Javob yozish» — or answered right there by replying
    to it. False when it could not go there."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from app.services import payments_chat

    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✍️ Javob yozish", callback_data=f"sup:pay:{ticket.id}")]]
    )
    hint = "\n\n<i>↩️ Javob berish: shu xabarga «Reply» qilib yozing.</i>"
    return await payments_chat.post(session, text + hint, markup, link=("ticket", ticket.id, ticket.user_id))


async def admin_reply(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    ticket_id: uuid.UUID,
    text: str,
    payment: bool = False,
    echo: bool = True,
) -> SupportMessage:
    """``payment``: an answer to a money question — the member continues in the same topic, and the
    answer is written in the payments chat too (``echo=False``: it was written there already, as a reply).
    ``actor_id`` is None for an answer posted in the payments channel (the channel signs it)."""
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
        text=f"📩 <b>Klub rahbariyatidan javob</b>\n\n{html.escape(body)}",
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
        after={"length": len(body)},
    )
    await session.commit()
    if payment and echo:
        from app.services import payments_chat

        member = await session.get(User, ticket.user_id)
        admin = await session.get(User, actor_id) if actor_id else None
        await payments_chat.post(
            session,
            f"↪️ <b>Javob</b> — {html.escape(admin.first_name if admin else '—')} → "
            f"{html.escape(member.full_name if member else '—')}\n\n{html.escape(body)}",
            link=("ticket", ticket.id, ticket.user_id),
        )
    return message


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
