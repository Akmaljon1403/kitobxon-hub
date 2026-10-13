"""Round M6: an admin sees and edits the saved stickers and premium emoji right in the bot —
not only in the Admin Panel. /stiker lists them with a delete button each; /emoji lists them with
per-emoji delete and keeps the «test» and «clear all» tools."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram.methods import SendSticker
from aiogram.types import Message, Sticker, Update
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelSticker, CustomEmoji
from app.services import custom_emoji
from tests.bot_helpers import BotHarness
from tests.factories import create_user
from tests.helpers import grant_role

_ids = itertools.count(996_500)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)
    custom_emoji.use({})
    custom_emoji.reset()


async def _super(db: AsyncSession) -> Any:
    user = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, user, "SUPER_ADMIN")
    return user


def _sticker(harness: BotHarness, unique: str) -> Update:
    sticker = Sticker(
        file_id=f"file-{unique}",
        file_unique_id=unique,
        type="regular",
        width=512,
        height=512,
        is_animated=False,
        is_video=False,
        emoji="🎉",
        set_name="Pack",
    )
    message = Message(
        message_id=next(_ids), date=datetime.now(UTC), chat=harness.chat, from_user=harness.user, sticker=sticker
    )
    return Update(update_id=next(_ids), message=message)


async def test_admin_sees_and_deletes_stickers_in_the_bot(db: AsyncSession) -> None:
    admin = await _super(db)
    harness = BotHarness(admin.telegram_id)
    await harness.send("/stiker")
    await harness.dispatcher.feed_update(harness.bot, _sticker(harness, "s1"))
    await harness.dispatcher.feed_update(harness.bot, _sticker(harness, "s2"))
    await harness.send("/tayyor")
    assert await db.scalar(select(func.count()).select_from(ChannelSticker)) == 2

    # /stiker now offers to view the saved ones
    harness.session.clear()
    await harness.send("/stiker")
    overview = harness.session.sent_messages()[-1]
    assert any(
        button.callback_data == "stk:list"
        for row in (overview.reply_markup.inline_keyboard if overview.reply_markup else [])
        for button in row
    )

    # pressing «list» sends each sticker with its own delete button
    harness.session.clear()
    await harness.press("stk:list")
    sent = [r for r in harness.session.requests if isinstance(r, SendSticker)]
    assert len(sent) == 2
    assert all(s.reply_markup.inline_keyboard[0][0].callback_data.startswith("stk:del:") for s in sent)

    # delete one — the club keeps the other
    victim = await db.scalar(select(ChannelSticker))
    await harness.press(f"stk:del:{victim.id}")
    assert await db.scalar(select(func.count()).select_from(ChannelSticker)) == 1


async def test_admin_sees_and_deletes_emoji_one_by_one(db: AsyncSession) -> None:
    admin = await _super(db)
    await custom_emoji.save(
        db,
        actor_id=admin.id,
        pairs=[("✋", "111", "✋"), ("❤", "222", "❤")],
    )
    assert await db.scalar(select(func.count()).select_from(CustomEmoji)) == 2

    harness = BotHarness(admin.telegram_id)
    await harness.send("/emoji")
    tools = harness.session.sent_messages()[-1]
    assert any(
        button.callback_data == "emj:list"
        for row in (tools.reply_markup.inline_keyboard if tools.reply_markup else [])
        for button in row
    )

    # «list» → a delete button per emoji
    harness.session.clear()
    await harness.press("emj:list")
    listed = harness.session.sent_messages()[-1]
    deletes = [
        button.callback_data
        for row in listed.reply_markup.inline_keyboard
        for button in row
        if button.callback_data.startswith("emj:del:")
    ]
    assert len(deletes) == 2

    # delete one emoji — the other stays
    await harness.press("emj:del:✋")
    rows = await custom_emoji.list_all(db)
    assert [row.emoji for row in rows] == ["❤"]
