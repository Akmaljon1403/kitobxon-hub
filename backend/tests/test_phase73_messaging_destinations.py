"""«📢 Xabarlar»: a manual post can go to the primary club channel or to an extra channel.

The destination selector offers the bot (members) and every configured channel; the per-post
``target_chat_id`` routes each post, and the sender publishes it to the right chat.
"""

from __future__ import annotations

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import SendMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.errors import BadRequestError
from app.models import ChannelPost, User
from app.models.enums import ChannelPostStatus
from app.security.permissions import Perm
from app.services import channel
from app.services.settings import update_setting
from app.workers.channel_sender import send_channel_posts
from tests.bot_helpers import BOT_TOKEN
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

from .test_phase30_channel import ChannelTelegram


async def _admin(db: AsyncSession) -> User:
    admin = await create_user(db, telegram_id=7_300_001)
    await db.commit()
    await grant_role(db, admin, "SUPER_ADMIN")
    await grant_permissions(db, admin, Perm.NOTIFICATION_SEND)
    return admin


def _bot(session: ChannelTelegram) -> Bot:
    return Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def test_parse_targets_reads_names_skips_rubbish() -> None:
    parsed = channel.parse_targets("Ustozlar=@kanalB, @kanalC, bad name!, @kanalB, -1001234567890")
    assert parsed == [
        {"chat_id": "@kanalB", "title": "Ustozlar"},
        {"chat_id": "@kanalC", "title": "@kanalC"},
        {"chat_id": "-1001234567890", "title": "-1001234567890"},
    ]
    assert channel.parse_targets("") == []


async def test_destinations_list_primary_then_extras(db: AsyncSession) -> None:
    admin = await _admin(db)
    await update_setting(db, key="channel.extra_targets", value="Ustozlar=@kanalB", actor_id=admin.id)
    dests = await channel.destinations(db)
    assert dests[0] == {"chat_id": "@FJSTIMutolaaxona", "title": "@FJSTIMutolaaxona", "primary": True}
    assert {"chat_id": "@kanalB", "title": "Ustozlar", "primary": False} in dests


async def test_manual_post_targets_an_extra_channel(db: AsyncSession) -> None:
    admin = await _admin(db)
    await update_setting(db, key="channel.extra_targets", value="@kanalB", actor_id=admin.id)

    to_extra = await channel.manual_post(db, actor_id=admin.id, text="Faqat B kanaliga", target_chat_id="@kanalB")
    assert to_extra.target_chat_id == "@kanalB"

    # The primary channel is stored as NULL (keeps automatic posts and dedup simple).
    to_primary = await channel.manual_post(db, actor_id=admin.id, text="Asosiyga", target_chat_id="@FJSTIMutolaaxona")
    assert to_primary.target_chat_id is None

    no_target = await channel.manual_post(db, actor_id=admin.id, text="Yana asosiyga")
    assert no_target.target_chat_id is None

    with pytest.raises(BadRequestError):
        await channel.manual_post(db, actor_id=admin.id, text="Begona", target_chat_id="@notlisted")


async def test_sender_publishes_to_the_chosen_channel(db: AsyncSession) -> None:
    admin = await _admin(db)
    await update_setting(db, key="channel.enabled", value=True, actor_id=admin.id)
    await update_setting(db, key="channel.extra_targets", value="Ustozlar=@kanalB", actor_id=admin.id)
    await channel.manual_post(
        db, actor_id=admin.id, text="B kanaliga post", with_button=False, target_chat_id="@kanalB"
    )
    await channel.manual_post(db, actor_id=admin.id, text="Asosiy kanalga post", with_button=False)

    telegram = ChannelTelegram()
    assert await send_channel_posts(get_session_factory(), _bot(telegram)) == 2
    chats = {r.text: r.chat_id for r in telegram.requests if isinstance(r, SendMessage)}
    assert chats["B kanaliga post"] == "@kanalB"
    assert chats["Asosiy kanalga post"] == "@FJSTIMutolaaxona"
    assert all(post.status == ChannelPostStatus.SENT for post in await db.scalars(select(ChannelPost)))


async def test_overview_lists_destinations(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    await update_setting(db, key="channel.extra_targets", value="Ustozlar=@kanalB", actor_id=admin.id)
    overview = (await client.get("/api/v1/admin/channel", headers=admin_headers(admin))).json()
    titles = [(t["title"], t["primary"]) for t in overview["targets"]]
    assert ("@FJSTIMutolaaxona", True) in titles
    assert ("Ustozlar", False) in titles
