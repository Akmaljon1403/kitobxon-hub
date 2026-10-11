"""Publishes queued posts in the club's Telegram channel (see ``app.services.channel``).

Claimed like notifications: a short lease on ``scheduled_at`` inside ``FOR UPDATE SKIP LOCKED``.
When Telegram refuses (the bot is not an administrator of the channel, the address is wrong) the
post is marked failed and the super admins are told once a day what to fix.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ChannelPost
from app.models.enums import ChannelPostKind, ChannelPostStatus, NotificationType
from app.services import channel
from app.services.settings import get_setting

logger = logging.getLogger(__name__)

LEASE = timedelta(minutes=5)
MAX_ATTEMPTS = 5
STALE_AFTER = timedelta(days=2)  # an automatic post this late is no longer news
CAPTION_LIMIT = 1024


async def _bot_username(bot: Bot) -> str | None:
    from app.bot.setup import resolve_bot_username

    return await resolve_bot_username(bot)


async def _markup(bot: Bot, buttons: list[dict[str, Any]] | None) -> InlineKeyboardMarkup | None:
    rows = []
    for spec in buttons or []:
        url = spec.get("url")
        if spec.get("bot_start") is not None:
            username = await _bot_username(bot)
            url = f"https://t.me/{username}?start={spec['bot_start']}" if username else None
        if url:
            rows.append([InlineKeyboardButton(text=spec["text"], url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _photo(post: ChannelPost) -> BufferedInputFile | str | None:
    if post.photo_key:
        from app.services.storage import get_storage

        try:
            return BufferedInputFile(await get_storage().get(post.photo_key), filename="post.jpg")
        except Exception:  # the text still goes out without the picture
            logger.warning("Channel post %s: picture %s is missing", post.id, post.photo_key)
            return None
    return post.photo_url


async def _claim(session: AsyncSession, limit: int) -> list[ChannelPost]:
    due = (
        select(ChannelPost.id)
        .where(ChannelPost.status == ChannelPostStatus.PENDING, ChannelPost.scheduled_at <= datetime.now(UTC))
        .order_by(ChannelPost.scheduled_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    claimed = list(
        await session.scalars(
            update(ChannelPost)
            .where(ChannelPost.id.in_(due.scalar_subquery()))
            .values(scheduled_at=datetime.now(UTC) + LEASE, attempts=ChannelPost.attempts + 1)
            .returning(ChannelPost)
            .execution_options(synchronize_session=False)
        )
    )
    await session.commit()
    claimed.sort(key=lambda post: post.created_at)
    return claimed


async def _extra_photos(post: ChannelPost) -> list[BufferedInputFile]:
    from app.services.storage import get_storage

    files = []
    for index, key in enumerate(post.extra_photo_keys or [], start=2):
        try:
            files.append(BufferedInputFile(await get_storage().get(key), filename=f"post-{index}.jpg"))
        except Exception:  # a missing picture does not stop the album
            logger.warning("Channel post %s: picture %s is missing", post.id, key)
    return files


async def _publish_album(
    bot: Bot, chat_id: str | int, post: ChannelPost, photo: BufferedInputFile | str, extra: list[BufferedInputFile]
) -> int:
    """Several pictures: an album (Telegram allows no buttons on it, so they follow in a short message)."""
    caption = post.text if len(post.text) <= CAPTION_LIMIT else None
    media = [InputMediaPhoto(media=photo, caption=caption)] + [InputMediaPhoto(media=item) for item in extra[:9]]
    messages = await bot.send_media_group(chat_id=chat_id, media=media)
    first = messages[0].message_id
    markup = await _markup(bot, post.buttons)
    if caption is None:
        first = (
            await bot.send_message(chat_id=chat_id, text=post.text, reply_markup=markup, disable_web_page_preview=True)
        ).message_id
    elif markup is not None:
        await bot.send_message(chat_id=chat_id, text="📸 Tadbirdan ko'proq lavhalar 👇", reply_markup=markup)
    return first


async def _publish(bot: Bot, chat_id: str | int, post: ChannelPost) -> int:
    photo = await _photo(post)
    extra = await _extra_photos(post) if photo is not None and post.extra_photo_keys else []
    if photo is not None and extra:
        return await _publish_album(bot, chat_id, post, photo, extra)
    markup = await _markup(bot, post.buttons)
    if photo is not None and len(post.text) <= CAPTION_LIMIT:
        message = await bot.send_photo(chat_id=chat_id, photo=photo, caption=post.text or None, reply_markup=markup)
    else:
        if photo is not None:
            await bot.send_photo(chat_id=chat_id, photo=photo)
        message = await bot.send_message(
            chat_id=chat_id, text=post.text, reply_markup=markup, disable_web_page_preview=True
        )
    if post.sticker_file_id:
        try:
            await bot.send_sticker(chat_id=chat_id, sticker=post.sticker_file_id)
        except TelegramBadRequest:
            logger.warning("Channel post %s: sticker could not be sent", post.id)
    return message.message_id


async def _tell_admins(session: AsyncSession, error: str) -> None:
    from app.services.notifications import enqueue_for_members, render
    from app.services.rbac import super_admins

    chat = await get_setting(session, "channel.chat_id")
    text = (
        f"⚠️ Kanalga ({chat}) post joylab bo'lmadi.\n\nTelegram javobi: {error[:300]}\n\n"
        "Tekshiring: bot kanalga administrator qilib qo'shilganmi va «Xabar joylash» huquqi bormi? "
        "Kanal manzili Sozlamalar → Telegram kanal bo'limida to'g'ri yozilganmi?"
    )
    await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=(await render(session, NotificationType.SYSTEM, message=text)) or text,
        dedup_prefix=f"channel_error:{datetime.now(UTC):%Y-%m-%d}",
        members=super_admins(),
        payload={"buttons": [{"text": "📢 Kanal", "admin_route": "channel"}]},
        priority=2,
    )


async def send_channel_posts(session_factory: async_sessionmaker[AsyncSession], bot: Bot, *, limit: int = 5) -> int:
    """Publish due channel posts. Returns how many were published."""
    async with session_factory() as session:
        if not await get_setting(session, "channel.enabled"):
            return 0
        chat_id = channel.normalize_chat_id(str(await get_setting(session, "channel.chat_id")))
        if chat_id is None:
            return 0
        await channel.request_reviews(session)  # the admins see automatic posts a few minutes before
        batch = await _claim(session, limit)
        published = 0
        for post in batch:
            if post.kind != ChannelPostKind.MANUAL and post.created_at < datetime.now(UTC) - STALE_AFTER:
                post.status = ChannelPostStatus.CANCELLED
                post.last_error = "eskirgan (kanal o'chiq turgan paytda navbatga qo'yilgan)"
                await session.commit()
                continue
            try:
                post.message_id = await _publish(bot, chat_id, post)
            except TelegramRetryAfter as exc:
                post.scheduled_at = datetime.now(UTC) + timedelta(seconds=exc.retry_after)
                post.attempts -= 1
                await session.commit()
                break
            except (TelegramForbiddenError, TelegramBadRequest) as exc:
                post.status = ChannelPostStatus.FAILED
                post.last_error = str(exc)[:500]
                await _tell_admins(session, str(exc))
            except Exception as exc:  # network problems, Telegram 5xx: try again later
                logger.warning("Channel post %s not sent (attempt %s): %s", post.id, post.attempts, exc)
                post.last_error = str(exc)[:500]
                if post.attempts >= MAX_ATTEMPTS:
                    post.status = ChannelPostStatus.FAILED
                else:
                    post.scheduled_at = datetime.now(UTC) + timedelta(seconds=60 * 2 ** (post.attempts - 1))
            else:
                post.status = ChannelPostStatus.SENT
                post.sent_at = datetime.now(UTC)
                post.last_error = None
                published += 1
            await session.commit()
    if published:
        logger.info("Channel: %s post(s) published", published)
    return published
