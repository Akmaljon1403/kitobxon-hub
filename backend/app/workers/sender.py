"""Delivers queued notifications through the Telegram bot.

Safe with several workers: a batch is *claimed* by pushing its ``scheduled_at`` a few minutes
into the future (a lease) inside a ``FOR UPDATE SKIP LOCKED`` statement, so no two workers
take the same message. If a worker dies mid-batch, the lease expires and the message is retried.
Telegram allows ~30 messages per second per bot; we stay below that.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models import Notification, NotificationTemplate, User, UserNotificationSettings
from app.models.enums import NotificationStatus, NotificationType, UserStatus
from app.services import stickers
from app.services.notifications import PREFERENCE_FIELD, STALE_AFTER

logger = logging.getLogger(__name__)

LEASE = timedelta(minutes=5)
MAX_ATTEMPTS = 5
SEND_INTERVAL_SECONDS = 1 / 25
CAPTION_LIMIT = 1024  # Telegram's limit for a file caption


@dataclass
class SendReport:
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    retried: int = 0
    errors: list[str] = field(default_factory=list)
    blocked: list[int] = field(default_factory=list)  # Telegram ids of members who blocked the bot

    @property
    def total(self) -> int:
        return self.sent + self.skipped + self.failed + self.retried


def _button(spec: dict[str, Any]) -> InlineKeyboardButton | None:
    settings = get_settings()
    if spec.get("app_route") is not None and settings.webapp_url:
        url = f"{settings.webapp_url}#/{spec['app_route']}" if spec["app_route"] else settings.webapp_url
        return InlineKeyboardButton(text=spec["text"], web_app=WebAppInfo(url=url))
    if spec.get("admin_route") is not None and settings.base_url:
        # The Admin Panel opens inside Telegram and signs in with the admin's Telegram account.
        url = f"{settings.base_url}/admin/#/{spec['admin_route']}"
        return InlineKeyboardButton(text=spec["text"], web_app=WebAppInfo(url=url))
    if spec.get("callback"):
        return InlineKeyboardButton(text=spec["text"], callback_data=spec["callback"])
    if spec.get("url"):
        return InlineKeyboardButton(text=spec["text"], url=spec["url"])
    return None


def _markup(payload: dict[str, Any] | None) -> InlineKeyboardMarkup | None:
    """Inline buttons: each entry is one button on its own line, or {"row": [...]} for one line."""
    rows = []
    for entry in (payload or {}).get("buttons") or []:
        specs = entry["row"] if "row" in entry else [entry]
        row = [button for button in (_button(spec) for spec in specs) if button is not None]
        if row:
            rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


# Mass messages wait for the morning during the club's quiet hours; personal and urgent ones
# (attendance, payments, test results, priority 1-2) always go.
QUIET_TYPES = (
    NotificationType.ADMIN_MESSAGE,
    NotificationType.ANNOUNCEMENT,
    NotificationType.NEW_BOOK,
    NotificationType.EVENT_CREATED,
    NotificationType.DIGEST,
    NotificationType.RANKING_UPDATE,
    NotificationType.ACHIEVEMENT_UNLOCKED,
    NotificationType.CERTIFICATE,
    NotificationType.REWARD,
    NotificationType.FEEDBACK_REQUEST,
)


async def quiet_until(session: AsyncSession, now: datetime) -> datetime | None:
    """The end of the quiet hours when ``now`` falls inside them (``notifications.quiet_hours``)."""
    from datetime import time as clock

    from app.services.settings import get_setting
    from app.utils.timezone import local_tz

    window = str(await get_setting(session, "notifications.quiet_hours") or "")
    if not window:
        return None
    start_text, end_text = window.split("-")
    start = clock.fromisoformat(start_text)
    end = clock.fromisoformat(end_text)
    local = now.astimezone(local_tz())
    current = local.time()
    inside = (start <= current or current < end) if start > end else (start <= current < end)
    if not inside or start == end:
        return None
    day = local.date() if current < end else local.date() + timedelta(days=1)
    return datetime.combine(day, end, tzinfo=local_tz())


async def _hold_for_morning(session: AsyncSession) -> None:
    """During the quiet hours, due mass messages move to the morning (the worker then sleeps till then)."""
    now = datetime.now(UTC)
    morning = await quiet_until(session, now)
    if morning is None:
        return
    await session.execute(
        update(Notification)
        .where(
            Notification.status == NotificationStatus.PENDING,
            Notification.scheduled_at <= now,
            Notification.type.in_(QUIET_TYPES),
            Notification.priority >= 3,
        )
        .values(scheduled_at=morning)
    )
    await session.commit()


async def _claim(session: AsyncSession, limit: int) -> list[Notification]:
    await _hold_for_morning(session)
    due = (
        select(Notification.id)
        .where(Notification.status == NotificationStatus.PENDING, Notification.scheduled_at <= datetime.now(UTC))
        .order_by(Notification.priority, Notification.scheduled_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    claimed = list(
        await session.scalars(
            update(Notification)
            .where(Notification.id.in_(due.scalar_subquery()))
            .values(scheduled_at=datetime.now(UTC) + LEASE, attempts=Notification.attempts + 1)
            .returning(Notification)
            .execution_options(synchronize_session=False)
        )
    )
    await session.commit()
    claimed.sort(key=lambda n: (n.priority, n.created_at))
    return claimed


def _finish(notification: Notification, status: NotificationStatus, error: str | None = None) -> None:
    notification.status = status
    notification.last_error = error[:500] if error else None
    if status == NotificationStatus.SENT:
        notification.sent_at = datetime.now(UTC)


async def _licence_staff(session: AsyncSession, user_ids: set[Any]) -> set[Any] | None:
    """None normally; while a rented copy's licence has ended, the administrators among ``user_ids``
    (only they still get messages)."""
    from app.core import licence

    if not licence.status().blocks_members:
        return None
    from app.models import Role, UserRole
    from app.services.rbac import ADMIN_ROLES

    return set(
        await session.scalars(
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids), Role.code.in_(ADMIN_ROLES))
        )
    )


async def send_due_notifications(
    session_factory: async_sessionmaker[AsyncSession], bot: Bot, *, limit: int = 100
) -> SendReport:
    """Send one batch of due messages. Returns what happened (for logs and tests)."""
    report = SendReport()
    async with session_factory() as session:
        batch = await _claim(session, limit)
        if not batch:
            return report
        users = {
            user.id: user for user in await session.scalars(select(User).where(User.id.in_({n.user_id for n in batch})))
        }
        preferences = {
            pref.user_id: pref
            for pref in await session.scalars(
                select(UserNotificationSettings).where(UserNotificationSettings.user_id.in_(users))
            )
        }
        critical = set(
            await session.scalars(select(NotificationTemplate.type).where(NotificationTemplate.is_critical.is_(True)))
        )
        now = datetime.now(UTC)
        staff_only = await _licence_staff(session, set(users))
        for index, notification in enumerate(batch):
            user = users.get(notification.user_id)
            type_ = NotificationType(notification.type)
            is_critical = type_ in critical or notification.priority <= 1
            pref_field = PREFERENCE_FIELD.get(type_)
            stale_after = STALE_AFTER.get(type_)
            deliver_anyway = bool((notification.payload or {}).get("deliver_to_inactive"))
            if user is None or user.deleted_at is not None or (user.status != UserStatus.ACTIVE and not deliver_anyway):
                _finish(notification, NotificationStatus.SKIPPED, "member is not active")
                report.skipped += 1
            elif staff_only is not None and user.id not in staff_only:
                _finish(notification, NotificationStatus.SKIPPED, "licence expired")
                report.skipped += 1
            elif (
                not is_critical
                and pref_field
                and user.id in preferences
                and not getattr(preferences[user.id], pref_field)
            ):
                _finish(notification, NotificationStatus.SKIPPED, f"member turned off {pref_field}")
                report.skipped += 1
            elif not is_critical and stale_after and notification.created_at < now - stale_after:
                _finish(notification, NotificationStatus.SKIPPED, "outdated")
                report.skipped += 1
            else:
                document = await _document(session, notification)
                mood = (notification.payload or {}).get("mood")
                retry_after = await _deliver(
                    bot,
                    notification,
                    user,
                    report,
                    document,
                    effect=stickers.EFFECTS.get(mood) if mood else None,
                    sticker=await stickers.pick(session, mood) if mood else None,
                )
                if retry_after is not None:
                    # Telegram asked us to slow down: put the rest of the batch back as well.
                    for waiting in batch[index + 1 :]:
                        waiting.scheduled_at = datetime.now(UTC) + timedelta(seconds=retry_after)
                        waiting.attempts -= 1
                    await session.commit()
                    break
                await asyncio.sleep(SEND_INTERVAL_SECONDS)
            await session.commit()
        if report.blocked:
            # Blocking the bot means leaving the club: the data is kept 30 days for a return.
            from app.services import membership

            for telegram_id in set(report.blocked):
                await membership.on_bot_blocked(session, telegram_id)
            await session.commit()
    if report.total:
        logger.info(
            "Notifications: %s sent, %s skipped, %s failed, %s retried",
            report.sent,
            report.skipped,
            report.failed,
            report.retried,
        )
    return report


async def _edit(bot: Bot, notification: Notification, user: User, report: SendReport, message_id: int) -> int | None:
    """Change a message already sent (a copy of an admin request that someone has dealt with)."""
    markup = _markup(notification.payload)
    try:
        try:
            await bot.edit_message_text(
                chat_id=user.telegram_id,
                message_id=message_id,
                text=notification.text,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
        except TelegramBadRequest as exc:
            if "no text in the message" not in str(exc).lower():
                raise
            await bot.edit_message_caption(  # the copy was a picture with a caption
                chat_id=user.telegram_id,
                message_id=message_id,
                caption=notification.text[:CAPTION_LIMIT],
                reply_markup=markup,
            )
    except TelegramRetryAfter as exc:
        notification.scheduled_at = datetime.now(UTC) + timedelta(seconds=exc.retry_after)
        notification.attempts -= 1
        report.retried += 1
        return int(exc.retry_after)
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        if "not modified" in str(exc).lower():
            _finish(notification, NotificationStatus.SENT)
            report.sent += 1
        else:  # deleted by the admin, too old to edit: nothing to update
            _finish(notification, NotificationStatus.SKIPPED, str(exc))
            report.skipped += 1
        return None
    except Exception as exc:
        if notification.attempts >= MAX_ATTEMPTS:
            _finish(notification, NotificationStatus.FAILED, str(exc))
            report.failed += 1
        else:
            notification.scheduled_at = datetime.now(UTC) + timedelta(seconds=30 * 2 ** (notification.attempts - 1))
            notification.last_error = str(exc)[:500]
            report.retried += 1
        return None
    notification.telegram_message_id = message_id
    _finish(notification, NotificationStatus.SENT)
    report.sent += 1
    return None


# A picture sent to many members is uploaded once: Telegram's file id is reused after the first send.
_photo_ids: dict[str, str] = {}


async def _photo(notification: Notification) -> str | BufferedInputFile | None:
    """The picture sent with the message (e.g. a member's quote card), from our storage."""
    key = (notification.payload or {}).get("photo_key")
    if not key:
        return None
    if key in _photo_ids:
        return _photo_ids[key]
    from app.services.storage import get_storage

    try:
        data = await get_storage().get(key)
    except Exception:  # the words still matter: send them without the picture
        logger.exception("Photo %s for notification %s is missing", key, notification.id)
        return None
    return BufferedInputFile(data, filename=key.rsplit("/", 1)[-1])


async def _document(session: AsyncSession, notification: Notification) -> BufferedInputFile | None:
    """The file sent together with the message (a certificate PDF), if any."""
    certificate_id = (notification.payload or {}).get("certificate_id")
    if not certificate_id:
        return None
    from app.services import certificates

    try:
        certificate = await certificates.get(session, uuid.UUID(certificate_id))
        if certificate.revoked_at is not None:
            return None
        data = await certificates.pdf_bytes(session, certificate)
        return BufferedInputFile(data, filename=certificates.filename(certificate))
    except Exception:  # the message itself still matters; the member can download the file later
        logger.exception("Certificate %s could not be attached", certificate_id)
        return None


async def _deliver(
    bot: Bot,
    notification: Notification,
    user: User,
    report: SendReport,
    document: BufferedInputFile | None = None,
    *,
    effect: str | None = None,
    sticker: str | None = None,
) -> int | None:
    """Send one message and record the outcome. Returns seconds to wait if rate-limited.
    ``effect``: Telegram's animated message effect (🎉); ``sticker``: sent right after the message."""

    edit_of = (notification.payload or {}).get("edit_of")
    if edit_of:
        return await _edit(bot, notification, user, report, int(edit_of))
    photo = await _photo(notification) if document is None else None

    async def send(effect_id: str | None) -> Message:
        if photo is not None and len(notification.text) <= CAPTION_LIMIT:
            sent = await bot.send_photo(
                chat_id=user.telegram_id,
                photo=photo,
                caption=notification.text,
                reply_markup=_markup(notification.payload),
                message_effect_id=effect_id,
            )
            key = (notification.payload or {}).get("photo_key")
            if key and sent.photo:
                _photo_ids[key] = sent.photo[-1].file_id
            return sent
        if document is not None and len(notification.text) <= CAPTION_LIMIT:
            return await bot.send_document(
                chat_id=user.telegram_id,
                document=document,
                caption=notification.text,
                reply_markup=_markup(notification.payload),
                message_effect_id=effect_id,
            )
        return await bot.send_message(
            chat_id=user.telegram_id,
            text=notification.text,
            reply_markup=_markup(notification.payload),
            disable_web_page_preview=True,
            message_effect_id=effect_id,
        )

    try:
        try:
            message = await send(effect)
        except TelegramBadRequest as exc:
            if effect is None or "effect" not in str(exc).lower():
                raise
            message = await send(None)  # the effect is a decoration: the message matters
    except TelegramRetryAfter as exc:
        notification.scheduled_at = datetime.now(UTC) + timedelta(seconds=exc.retry_after)
        notification.attempts -= 1
        report.retried += 1
        return int(exc.retry_after)
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        # The member blocked the bot or the chat does not exist: retrying will not help.
        _finish(notification, NotificationStatus.FAILED, str(exc))
        report.failed += 1
        report.errors.append(str(exc))
        if isinstance(exc, TelegramForbiddenError) and "blocked" in str(exc).lower():
            report.blocked.append(user.telegram_id)
        return None
    except Exception as exc:  # network problems, Telegram 5xx: try again later
        logger.warning("Notification %s not sent (attempt %s): %s", notification.id, notification.attempts, exc)
        if notification.attempts >= MAX_ATTEMPTS:
            _finish(notification, NotificationStatus.FAILED, str(exc))
            report.failed += 1
        else:
            notification.scheduled_at = datetime.now(UTC) + timedelta(seconds=30 * 2 ** (notification.attempts - 1))
            notification.last_error = str(exc)[:500]
            report.retried += 1
        report.errors.append(str(exc))
        return None
    notification.telegram_message_id = message.message_id
    _finish(notification, NotificationStatus.SENT)
    report.sent += 1
    if sticker:
        try:
            await bot.send_sticker(chat_id=user.telegram_id, sticker=sticker)
        except Exception:  # decoration only
            logger.info("Notification %s: the sticker could not be sent", notification.id)
    return None
