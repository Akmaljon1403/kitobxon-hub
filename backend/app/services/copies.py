"""One message, many copies: what several admins received about the same thing stays the same for all.

A request that waits for a decision (a member's question, a receipt, a text to moderate, a manual
attendance, a restore request, a channel post to review) reaches every admin who may decide — each in
their own chat with the bot, and sometimes in the payments channel too. When one of them acts (in the
bot, in the channel or in the Admin Panel), every copy shows it: «✅ Javob berildi — Dilnoza A., 14:05»,
with the buttons that still make sense. Nobody answers twice, and the super admin always sees the state.

How: such messages carry a ``sync_key`` (e.g. ``ticket:<id>``). ``settle`` rewrites every copy:
copies not sent yet are changed in place; sent ones get an *edit* queued for the sender (``edit_of``),
which retries and respects Telegram's limits like any other message. Payments-chat posts linked to the
same thing (``PaymentsChatLink`` with ``base_text``) are edited directly.
"""

from __future__ import annotations

import contextvars
import html
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Notification, User
from app.models.enums import NotificationStatus
from app.utils.timezone import local_tz

logger = logging.getLogger(__name__)

TEXT_LIMIT = 4000
# (chat id, message id) of the button just pressed: that copy is updated by the handler itself.
pressed: contextvars.ContextVar[tuple[int, int] | None] = contextvars.ContextVar("pressed_copy", default=None)


def pressed_here(callback: Any) -> None:
    """The handler shows the outcome on the message whose button was pressed; ``settle`` leaves that copy."""
    message = getattr(callback, "message", None)
    chat = getattr(message, "chat", None)
    if message is not None and chat is not None:
        pressed.set((chat.id, message.message_id))


def stamp(moment: datetime | None = None) -> str:
    """«14:05» today, «12.10 14:05» on another day (the club's time)."""
    local = (moment or datetime.now(UTC)).astimezone(local_tz())
    today = datetime.now(UTC).astimezone(local_tz()).date()
    return f"{local:%H:%M}" if local.date() == today else f"{local:%d.%m %H:%M}"


async def admin_name(session: AsyncSession, user_id: uuid.UUID | None) -> str:
    """«Dilnoza Aliyeva» — for the admins' eyes only (members never learn who answered)."""
    if user_id is None:
        return "—"
    user = await session.get(User, user_id)
    if user is None:
        return "—"
    return html.escape(f"{user.first_name} {user.last_name or ''}".strip(), quote=False)


def compose(base: str, status: str | None) -> str:
    text = f"{base}\n\n{status}" if status else base
    return text if len(text) <= TEXT_LIMIT else text[: TEXT_LIMIT - 1] + "…"


async def settle(
    session: AsyncSession,
    key: str,
    status: str,
    *,
    buttons: list[dict[str, Any]] | None = None,
    payments_buttons: Any = None,
) -> int:
    """Show ``status`` under every copy of ``key`` (the caller commits). ``buttons``: the copies' new
    buttons (None — none left). ``payments_buttons``: an aiogram keyboard for the payments-chat posts.
    Returns how many copies were touched."""
    rows = list(await session.scalars(select(Notification).where(Notification.sync_key == key)))
    skip = pressed.get()
    telegram_ids: dict[uuid.UUID, int] = {}
    if rows:
        telegram_ids = dict(
            (
                await session.execute(
                    select(User.id, User.telegram_id).where(User.id.in_({row.user_id for row in rows}))
                )
            ).all()
        )
    touched = 0
    for row in rows:
        payload = dict(row.payload or {})
        base = payload.get("base") or row.text
        payload.update(base=base, status=status, buttons=buttons or [])
        text = compose(base, status)
        if row.status == NotificationStatus.PENDING:
            row.text, row.payload = text, payload
            flag_modified(row, "payload")
            touched += 1
            continue
        mine = skip is not None and (telegram_ids.get(row.user_id), row.telegram_message_id) == skip
        row.payload = payload
        flag_modified(row, "payload")
        if row.status != NotificationStatus.SENT or not row.telegram_message_id or mine:
            continue
        session.add(
            Notification(
                user_id=row.user_id,
                type=row.type,
                text=text,
                payload={"edit_of": row.telegram_message_id, "buttons": buttons or []},
                priority=0,
            )
        )
        touched += 1
    touched += await _settle_payments_chat(session, key, status, payments_buttons)
    if touched:
        from app.services.notifications import wake_sender

        wake_sender()
    return touched


async def _settle_payments_chat(session: AsyncSession, key: str, status: str, markup: Any) -> int:
    """The posts in the payments chat about the same thing (a payment question)."""
    kind, _, target = key.partition(":")
    if kind != "ticket":
        return 0
    from app.models import PaymentsChatLink
    from app.services.delivery import optional_bot

    try:
        target_id = uuid.UUID(target)
    except ValueError:
        return 0
    links = list(
        await session.scalars(
            select(PaymentsChatLink).where(
                PaymentsChatLink.kind == "ticket",
                PaymentsChatLink.target_id == target_id,
                PaymentsChatLink.base_text.is_not(None),
            )
        )
    )
    bot = optional_bot() if links else None
    if bot is None:
        return 0
    skip = pressed.get()
    edited = 0
    for link in links:
        if skip is not None and (link.chat_id, link.message_id) == skip:
            continue
        try:
            await bot.edit_message_text(
                compose(link.base_text or "", status),
                chat_id=link.chat_id,
                message_id=link.message_id,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
            edited += 1
        except Exception as exc:  # deleted by an admin, or nothing changed: the answer itself is out
            if "not modified" not in str(exc).lower():
                logger.info("A payments chat post could not be updated: %s", exc)
    return edited
