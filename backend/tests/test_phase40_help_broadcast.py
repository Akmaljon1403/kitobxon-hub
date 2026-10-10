"""Round E9–E10: questions and answers in the bot and the app, writing to the club from the app and
while blocked, the screen for members who left, /stop, and broadcasts with buttons and a preview."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import httpx
from aiogram.methods import DeleteMessages
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.models import Notification, SupportMessage
from app.models.enums import UserStatus
from app.security.permissions import Perm
from app.services import faq
from tests.bot_helpers import BotHarness
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

_ids = itertools.count(1_600_000)


async def test_questions_and_answers_in_the_bot(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    harness = BotHarness(member.telegram_id)
    await harness.press("faq:list")
    topics = harness.session.sent_messages()[-1].reply_markup.inline_keyboard
    codes = [button.callback_data for row in topics for button in row if button.callback_data]
    assert codes == [f"faq:t:{topic.code}" for topic in faq.TOPICS]
    await harness.press("faq:t:tests")
    answer = harness.last_text()
    assert "Testni necha marta yechsa bo'ladi?" in answer and "davomatsiz" in answer
    await harness.press("faq:t:nope")  # an old button: nothing breaks


async def test_faq_and_writing_to_the_club_in_the_app(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.SUPPORT_MANAGE)
    topics = (await client.get("/api/v1/meta/faq")).json()
    assert [topic["code"] for topic in topics] == [topic.code for topic in faq.TOPICS]
    assert all(topic["items"] and topic["items"][0]["q"] for topic in topics)

    headers = member_headers(member)
    assert (await client.get("/api/v1/me/support", headers=headers)).json() == []
    sent = await client.post(
        "/api/v1/me/support", json={"text": "Sertifikatim chiqmadi", "topic": "general"}, headers=headers
    )
    assert sent.status_code == 200, sent.text
    assert [m["text"] for m in sent.json()] == ["Sertifikatim chiqmadi"]
    note = await db.scalar(select(Notification).where(Notification.user_id == admin.id))
    assert note is not None and "Sertifikatim chiqmadi" in note.text


async def test_a_blocked_member_can_still_write_and_get_the_answer(db: AsyncSession) -> None:
    from app.services import support

    member = await create_user(db, telegram_id=next(_ids), status=UserStatus.BLOCKED)
    admin = await create_user(db)
    await db.commit()
    harness = BotHarness(member.telegram_id)
    await harness.send("salom")
    reply = harness.session.sent_messages()[-1]
    assert reply.text == texts.ACCOUNT_BLOCKED
    assert reply.reply_markup.inline_keyboard[0][0].callback_data == "sup:new"
    await harness.press("sup:new")
    assert harness.last_text() == texts.SUPPORT_ASK
    await harness.send("Nega bloklandim?")
    assert harness.last_text() == texts.SUPPORT_SENT
    message = await db.scalar(select(SupportMessage).where(SupportMessage.text == "Nega bloklandim?"))
    assert message is not None
    await support.admin_reply(db, actor_id=admin.id, ticket_id=message.ticket_id, text="Davomatdagi xato uchun")
    await db.commit()
    answer = await db.scalar(
        select(Notification).where(Notification.user_id == member.id, Notification.type == "SUPPORT")
    )
    assert answer.payload["deliver_to_inactive"] is True  # the sender does not skip a blocked member

    # From the app's «blocked» screen the bot opens straight in «write to the admins».
    other = BotHarness(member.telegram_id)
    await other.send("/start support")
    assert other.last_text() == texts.SUPPORT_ASK


async def test_a_member_who_left_sees_two_buttons(db: AsyncSession) -> None:
    member = await create_user(
        db, telegram_id=next(_ids), status=UserStatus.LEFT, left_at=datetime.now(UTC) - timedelta(days=2)
    )
    await db.commit()
    harness = BotHarness(member.telegram_id)
    await harness.send("salom")
    reply = harness.session.sent_messages()[-1]
    assert reply.text == texts.LEFT_RESTRICTED
    first, second = reply.reply_markup.inline_keyboard
    assert first[0].url == "https://t.me/kitobxon_test_bot?start=qayta"  # sends /start by itself
    assert second[0].callback_data == "mem:wipe"
    await harness.press("mem:wipe")
    assert any(isinstance(request, DeleteMessages) for request in harness.session.requests)
    assert harness.last_text() == texts.LEFT_WIPED
    await harness.send("/start qayta")  # what the «🔄 Qayta tiklash» link sends
    offer = harness.session.sent_messages()[-1]
    assert offer.reply_markup.inline_keyboard[0][0].callback_data == "mem:restore"  # restore within 14 days


async def test_stop_ends_whatever_was_going_on(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    harness = BotHarness(member.telegram_id)
    await harness.press("sup:new")
    await harness.send("/stop")
    assert harness.last_text() == texts.STOPPED
    await harness.send("Bu endi adminga ketmaydi")
    assert await db.scalar(select(SupportMessage).where(SupportMessage.text == "Bu endi adminga ketmaydi")) is None


async def test_broadcast_with_buttons_preview_and_a_test_to_me(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db)
    members = [await create_user(db) for _ in range(2)]
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.NOTIFICATION_SEND)
    headers = admin_headers(admin)
    body = {
        "message": "Ertaga <test> bo'ladi",
        "buttons": "Ro'yxat | https://forms.gle/abc\nKanal | t.me/FJSTIMutolaaxona",
        "with_app_button": True,
    }
    preview = await client.post("/api/v1/admin/notifications/broadcast/preview", json=body, headers=headers)
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert "&lt;test&gt;" in data["text"]  # the admin's words are escaped
    assert [(b["text"], b["url"], b["kind"]) for b in data["buttons"]] == [
        ("Ro'yxat", "https://forms.gle/abc", "url"),
        ("Kanal", "https://t.me/FJSTIMutolaaxona", "url"),
        ("📱 Ilovada ochish", "", "app"),
    ]
    assert data["recipients"] >= 2

    bad = await client.post(
        "/api/v1/admin/notifications/broadcast/preview", json={**body, "buttons": "Faqat matn"}, headers=headers
    )
    assert bad.status_code == 400 and "1-qator" in bad.json()["error"]["message"]

    test = await client.post("/api/v1/admin/notifications/broadcast", json={**body, "test": True}, headers=headers)
    assert test.json()["recipients"] == 1
    mine = await db.scalar(select(Notification).where(Notification.user_id == admin.id))
    assert mine.text.startswith("🧪") and len(mine.payload["buttons"]) == 3

    sent = await client.post("/api/v1/admin/notifications/broadcast", json=body, headers=headers)
    assert sent.json()["recipients"] >= 2
    note = await db.scalar(select(Notification).where(Notification.user_id == members[0].id))
    assert note.payload["buttons"][0] == {"text": "Ro'yxat", "url": "https://forms.gle/abc"}
