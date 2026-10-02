"""Delivers queued notifications through the Telegram bot.

Safe with several workers: a batch is *claimed* by pushing its ``scheduled_at`` a few minutes
into the future (a lease) inside a ``FOR UPDATE SKIP LOCKED`` statement, so no two workers
take the same message. If a worker dies mid-batch, the lease expires and the message is retried.
Telegram allows ~30 messages per second per bot; we stay below that.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models import Notification, NotificationTemplate, User, UserNotificationSettings
from app.models.enums import NotificationStatus, NotificationType, UserStatus
from app.services.notifications import PREFERENCE_FIELD, STALE_AFTER

logger = logging.getLogger(__name__)

LEASE = timedelta(minutes=5)
MAX_ATTEMPTS = 5
SEND_INTERVAL_SECONDS = 1 / 25


@dataclass
class SendReport:
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    retried: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.sent + self.skipped + self.failed + self.retried


def _markup(payload: dict[str, Any] | None) -> InlineKeyboardMarkup | None:
    buttons = (payload or {}).get("buttons") or []
    webapp_url = get_settings().webapp_url
    rows = []
    admin_url = f"{get_settings().base_url}/admin/" if get_settings().base_url else None
    for button in buttons:
        if button.get("app_route") is not None and webapp_url:
            url = f"{webapp_url}#/{button['app_route']}" if button["app_route"] else webapp_url
            rows.append([InlineKeyboardButton(text=button["text"], web_app=WebAppInfo(url=url))])
        elif button.get("admin_route") is not None and admin_url:
            # The Admin Panel opens inside Telegram and signs in with the admin's Telegram account.
            rows.append(
                [
                    InlineKeyboardButton(
                        text=button["text"], web_app=WebAppInfo(url=f"{admin_url}#/{button['admin_route']}")
                    )
                ]
            )
        elif button.get("callback"):
            rows.append([InlineKeyboardButton(text=button["text"], callback_data=button["callback"])])
        elif button.get("url"):
            rows.append([InlineKeyboardButton(text=button["text"], url=button["url"])])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _claim(session: AsyncSession, limit: int) -> list[Notification]:
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
        for index, notification in enumerate(batch):
            user = users.get(notification.user_id)
            type_ = NotificationType(notification.type)
            is_critical = type_ in critical or notification.priority <= 1
            pref_field = PREFERENCE_FIELD.get(type_)
            stale_after = STALE_AFTER.get(type_)
            if user is None or user.deleted_at is not None or user.status != UserStatus.ACTIVE:
                _finish(notification, NotificationStatus.SKIPPED, "member is not active")
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
                retry_after = await _deliver(bot, notification, user, report)
                if retry_after is not None:
                    # Telegram asked us to slow down: put the rest of the batch back as well.
                    for waiting in batch[index + 1 :]:
                        waiting.scheduled_at = datetime.now(UTC) + timedelta(seconds=retry_after)
                        waiting.attempts -= 1
                    await session.commit()
                    break
                await asyncio.sleep(SEND_INTERVAL_SECONDS)
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


async def _deliver(bot: Bot, notification: Notification, user: User, report: SendReport) -> int | None:
    """Send one message and record the outcome. Returns seconds to wait if rate-limited."""
    try:
        message = await bot.send_message(
            chat_id=user.telegram_id,
            text=notification.text,
            reply_markup=_markup(notification.payload),
            disable_web_page_preview=True,
        )
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
    return None
