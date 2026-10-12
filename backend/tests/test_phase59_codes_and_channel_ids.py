"""Round K6: checking a certificate by its code without a QR scanner (/v), and the «-100…» channel id: an
admin forwards a channel post to the bot and gets the number for the settings."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import httpx
from aiogram.types import Chat, Message, MessageOriginChannel, Update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from tests.bot_helpers import BotHarness
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role

_ids = itertools.count(3_300_000)


async def test_a_certificate_is_checked_by_its_code(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await create_user(db, telegram_id=next(_ids))
    member = await create_user(db, telegram_id=next(_ids), first_name="Madina", last_name="Karimova")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    created = await client.post(
        "/api/v1/admin/certificates",
        json={"user_id": str(member.id), "title": "Faol kitobxon", "description": "Faol ishtiroki uchun."},
        headers=admin_headers(boss),
    )
    code = created.json()["code"]  # printed like K7F2Q-9XA3B

    page = await client.get("/v")
    assert page.status_code == 200 and 'action="/v"' in page.text and "QR kodni skanerlash shart emas" in page.text
    typed = await client.get("/v", params={"code": f"  {code.lower()} "}, follow_redirects=False)
    assert typed.status_code == 303 and typed.headers["location"] == f"/v/{code.replace('-', '')}"
    found = await client.get(typed.headers["location"])
    assert found.status_code == 200 and "Haqiqiy sertifikat" in found.text and "Karimova Madina" in found.text
    assert 'action="/v"' not in found.text  # a found document shows no search box

    missing = await client.get("/v/ABCDE12345")
    assert missing.status_code == 404 and 'action="/v"' in missing.text and 'value="ABCDE12345"' in missing.text


def _forward(harness: BotHarness, chat: Chat) -> Update:
    origin = MessageOriginChannel(type="channel", date=datetime.now(UTC), chat=chat, message_id=7)
    message = Message(
        message_id=next(_ids),
        date=datetime.now(UTC),
        chat=harness.chat,
        from_user=harness.user,
        text="Kanal posti",
        forward_origin=origin,
    )
    return Update(update_id=next(_ids), message=message)


async def test_a_forwarded_channel_post_tells_its_id(db: AsyncSession) -> None:
    admin = await create_user(db, telegram_id=next(_ids))
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    closed = Chat(id=-1001234567890, type="channel", title="Kitobxon — to'lovlar")
    harness = BotHarness(admin.telegram_id)
    await harness.dispatcher.feed_update(harness.bot, _forward(harness, closed))
    reply = harness.last_text()
    assert "<code>-1001234567890</code>" in reply and "Kitobxon — to'lovlar" in reply and "-100" in reply

    public = Chat(id=-1009876543210, type="channel", title="Klub", username="FJSTIMutolaaxona")
    await harness.dispatcher.feed_update(harness.bot, _forward(harness, public))
    assert "@FJSTIMutolaaxona" in harness.last_text()

    # a member's forward is not answered with ids (it goes on, e.g. as a message to the admins)
    plain = BotHarness(member.telegram_id)
    await plain.dispatcher.feed_update(plain.bot, _forward(plain, closed))
    assert "-1001234567890" not in plain.all_text()
    assert texts.CHAT_ID_HIDDEN not in plain.all_text()
