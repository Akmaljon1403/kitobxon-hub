"""Round L6–L8: one question, every admin sees the same state. Copies show «⏳ javob kutmoqda» and the whole
message; when one admin answers (bot, channel or panel) all copies say «✅ Javob berildi — who: what»;
«📄 Batafsil» brings the whole conversation; money questions are answered right in the payments channel by
the super admins and the admins given «💳 To'lov savollari»."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import EditMessageText, SendPhoto
from aiogram.types import CallbackQuery, Chat, Message, Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.database import get_session_factory
from app.models import Notification, PaymentsChatLink, SupportMessage, SupportTicket, User
from app.models.enums import NotificationStatus, SupportTicketStatus
from app.security.permissions import Perm
from app.services import support
from app.services.settings import update_setting
from app.workers import sender as sender_module
from app.workers.sender import send_due_notifications
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

sender_module.SEND_INTERVAL_SECONDS = 0
_ids = itertools.count(3_600_000)
CHANNEL = -1007778889990


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> FakeTelegramSession:
    session = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)
    return session


def _bot(session: FakeTelegramSession) -> Bot:
    return Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def _people(db: AsyncSession) -> dict[str, User]:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmal", last_name="Bosh")
    helper = await create_user(db, telegram_id=next(_ids), first_name="Dilnoza", last_name="Aliyeva")
    cashier = await create_user(db, telegram_id=next(_ids), first_name="Sardor", last_name="Kassir")
    other = await create_user(db, telegram_id=next(_ids), first_name="Boshqa", last_name="Admin")
    member = await create_user(db, telegram_id=next(_ids), first_name="Nodir", last_name="Qodirov")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    for admin in (helper, cashier, other):
        await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, helper, Perm.SUPPORT_MANAGE)
    await grant_permissions(db, cashier, Perm.PAYMENT_SUPPORT)
    return {"boss": boss, "helper": helper, "cashier": cashier, "other": other, "member": member}


async def _copies(db: AsyncSession, ticket_id: object) -> list[Notification]:
    return list(
        await db.scalars(
            select(Notification)
            .where(Notification.sync_key == f"ticket:{ticket_id}")
            .order_by(Notification.user_id)
            .execution_options(populate_existing=True)
        )
    )


async def test_every_copy_shows_who_answered(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession
) -> None:
    people = await _people(db)
    long_text = "Kitob topshirish muddati haqida savolim bor. " * 60  # ~2700 characters
    ticket = await support.member_message(db, user=people["member"], text=long_text)
    await db.commit()

    copies = await _copies(db, ticket.id)
    assert {copy.user_id for copy in copies} == {people["boss"].id, people["helper"].id}  # SUPPORT_MANAGE + boss
    for copy in copies:
        assert long_text.strip()[:2000] in copy.text  # the whole message, not a short preview
        assert copy.text.endswith(support.WAITING)
        row = copy.payload["buttons"][0]["row"]
        assert [button["text"] for button in row] == ["✍️ Javob yozish", "📄 Batafsil"]

    # the copies go out; then the helper answers in the Admin Panel
    sent = FakeTelegramSession()
    await send_due_notifications(get_session_factory(), _bot(sent))
    copies = await _copies(db, ticket.id)
    assert all(copy.status == NotificationStatus.SENT and copy.telegram_message_id for copy in copies)
    first = {copy.user_id: copy.telegram_message_id for copy in copies}

    answered = await client.post(
        f"/api/v1/admin/support/{ticket.id}/reply",
        json={"text": "Muddat — 25-oktabrgacha."},
        headers=admin_headers(people["helper"]),
    )
    assert answered.status_code in (200, 201), answered.text

    edits = list(
        await db.scalars(
            select(Notification).where(
                Notification.payload["edit_of"].is_not(None), Notification.status == NotificationStatus.PENDING
            )
        )
    )
    assert {edit.user_id for edit in edits} == {people["boss"].id, people["helper"].id}
    for edit in edits:
        assert "✅ <b>Javob berildi</b> — Dilnoza Aliyeva" in edit.text and "25-oktabrgacha" in edit.text
        assert edit.payload["edit_of"] == first[edit.user_id]

    # the sender changes the messages already in the admins' chats
    edited = FakeTelegramSession()
    await send_due_notifications(get_session_factory(), _bot(edited))
    changes = [r for r in edited.requests if isinstance(r, EditMessageText)]
    boss_change = next(r for r in changes if r.chat_id == people["boss"].telegram_id)
    assert boss_change.message_id == first[people["boss"].id] and "Javob berildi" in boss_change.text
    assert boss_change.reply_markup.inline_keyboard[0][0].text == "✍️ Yana yozish"

    # «🔒 Yopish» in the bot: every copy says it is closed
    boss = BotHarness(people["boss"].telegram_id)
    await boss.press(f"sup:close:{ticket.id}")
    assert texts.SUPPORT_CLOSED in boss.session.alerts()
    closed = await db.scalar(
        select(SupportTicket).where(SupportTicket.id == ticket.id).execution_options(populate_existing=True)
    )
    assert closed.status == SupportTicketStatus.CLOSED
    closing = await db.scalar(
        select(Notification).where(Notification.text.like("%Yopildi%"), Notification.user_id == people["helper"].id)
    )
    assert closing is not None and "Akmal Bosh" in closing.text


async def test_copies_not_sent_yet_are_changed_in_place(db: AsyncSession, telegram: FakeTelegramSession) -> None:
    people = await _people(db)
    ticket = await support.member_message(db, user=people["member"], text="Sertifikatim qachon chiqadi?")
    await db.commit()
    await support.admin_reply(db, actor_id=people["helper"].id, ticket_id=ticket.id, text="Ertaga.")
    copies = await _copies(db, ticket.id)
    assert all(copy.status == NotificationStatus.PENDING for copy in copies)
    assert all("Javob berildi" in copy.text and "Ertaga." in copy.text for copy in copies)
    edits = await db.scalar(select(Notification).where(Notification.payload["edit_of"].is_not(None)))
    assert edits is None  # nothing to edit: they go out already answered


async def test_more_shows_the_whole_conversation(db: AsyncSession, telegram: FakeTelegramSession) -> None:
    people = await _people(db)
    ticket = await support.member_message(db, user=people["member"], text="Birinchi xabar.")
    await support.member_message(db, user=people["member"], text="Ikkinchi, uzunroq xabar " * 20, photo_file_id="PH1")
    await db.commit()
    second = await db.scalar(
        select(Notification).where(Notification.sync_key == f"ticket:{ticket.id}", Notification.text.like("%2-xabar%"))
    )
    assert second is not None and "📷" in second.text

    helper = BotHarness(people["helper"].telegram_id)
    await helper.press(f"sup:full:{ticket.id}")
    thread = "\n".join(m.text for m in helper.session.sent_messages())
    assert "Murojaat to'liq" in thread and "Birinchi xabar." in thread and thread.count("👤 <b>A'zo</b>") == 2
    assert any(isinstance(r, SendPhoto) and r.photo == "PH1" for r in helper.session.requests)

    # without the right — nothing
    other = BotHarness(people["other"].telegram_id)
    await other.press(f"sup:full:{ticket.id}")
    assert texts.SUPPORT_NO_PERMISSION in other.session.alerts()
    assert not other.session.sent_messages()


async def _press(harness: BotHarness, data: str, chat: Chat, message_id: int) -> None:
    message = Message(message_id=message_id, date=datetime.now(UTC), chat=chat, text="💳 To'lov bo'yicha murojaat")
    callback = CallbackQuery(id=str(next(_ids)), from_user=harness.user, chat_instance="c", data=data, message=message)
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), callback_query=callback))


async def _channel_reply(harness: BotHarness, chat: Chat, to: int, text: str, signature: str | None = None) -> None:
    original = Message(message_id=to, date=datetime.now(UTC), chat=chat, text="…")
    post = Message(
        message_id=next(_ids),
        date=datetime.now(UTC),
        chat=chat,
        text=text,
        reply_to_message=original,
        author_signature=signature,
    )
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), channel_post=post))


async def test_money_questions_answered_in_the_channel(db: AsyncSession, telegram: FakeTelegramSession) -> None:
    people = await _people(db)
    await update_setting(db, key="payments.chat_id", value=str(CHANNEL), actor_id=people["boss"].id)
    channel = Chat(id=CHANNEL, type="channel", title="To'lovlar")
    ticket = await support.member_message(db, user=people["member"], text="Premium yoqilmadi", topic="payment")
    await db.commit()
    question = next(m for m in telegram.sent_messages() if "To'lov bo'yicha murojaat" in (m.text or ""))
    assert support.WAITING in question.text and "Premium yoqilmadi" in question.text
    assert [b.text for b in question.reply_markup.inline_keyboard[0]] == ["✍️ Javob yozish", "📄 Batafsil"]
    link = await db.scalar(select(PaymentsChatLink).where(PaymentsChatLink.target_id == ticket.id))
    assert link.base_text and support.WAITING not in link.base_text

    # an admin without the right cannot take it; the one given «💳 To'lov savollari» can
    other = BotHarness(people["other"].telegram_id)
    await _press(other, f"sup:pay:{ticket.id}", channel, link.message_id)
    assert texts.SUPPORT_PAYMENT_NO_RIGHT in other.session.alerts()
    cashier = BotHarness(people["cashier"].telegram_id)
    await _press(cashier, f"sup:pay:{ticket.id}", channel, link.message_id)
    assert texts.SUPPORT_REPLY_CHANNEL_HINT in cashier.session.alerts()
    taken = next(r for r in telegram.requests if isinstance(r, EditMessageText) and "javob yozmoqda" in r.text)
    assert taken.chat_id == CHANNEL and taken.message_id == link.message_id and "Sardor Kassir" in taken.text

    # the reply in the channel is the cashier's (the channel itself has no author)
    await _channel_reply(cashier, channel, link.message_id, "Premium yoqildi, tekshirib ko'ring.")
    answer = await db.scalar(select(SupportMessage).where(SupportMessage.from_admin.is_(True)))
    assert answer.admin_id == people["cashier"].id
    done = [r for r in telegram.requests if isinstance(r, EditMessageText) and "Javob berildi" in r.text]
    assert done and "Sardor Kassir" in done[-1].text and "Premium yoqildi" in done[-1].text

    # «📄 Batafsil» in the channel answers right there, and a «Reply» to it also reaches the member
    await _press(cashier, f"sup:full:p:{ticket.id}", channel, link.message_id)
    full = [m for m in cashier.session.sent_messages() if "Murojaat to'liq" in (m.text or "")]
    assert full and full[0].chat_id == CHANNEL and full[0].reply_to_message_id == link.message_id


async def test_payment_admins_answer_in_a_group_and_in_the_bot(db: AsyncSession, telegram: FakeTelegramSession) -> None:
    people = await _people(db)
    group = Chat(id=-1001112223334, type="supergroup", title="To'lovlar guruhi")
    await update_setting(db, key="payments.chat_id", value=str(group.id), actor_id=people["boss"].id)
    ticket = await support.member_message(db, user=people["member"], text="Karta qabul qilinmadi", topic="payment")
    await db.commit()
    link = await db.scalar(select(PaymentsChatLink).where(PaymentsChatLink.target_id == ticket.id))

    cashier = BotHarness(people["cashier"].telegram_id)
    original = Message(message_id=link.message_id, date=datetime.now(UTC), chat=group, text="…")
    reply = Message(
        message_id=next(_ids),
        date=datetime.now(UTC),
        chat=group,
        from_user=cashier.user,
        text="Iltimos, chekni qayta yuboring.",
        reply_to_message=original,
    )
    await cashier.dispatcher.feed_update(cashier.bot, Update(update_id=next(_ids), message=reply))
    answer = await db.scalar(select(SupportMessage).where(SupportMessage.from_admin.is_(True)))
    assert answer is not None and answer.admin_id == people["cashier"].id

    # without a payments chat: the copies go to the super admins and the cashier, who answer in the bot
    await update_setting(db, key="payments.chat_id", value="", actor_id=people["boss"].id)
    again = await support.member_message(db, user=people["member"], text="Rahmat, yana bir savol", topic="payment")
    await db.commit()
    copies = await _copies(db, again.id)
    assert {people["boss"].id, people["cashier"].id} <= {copy.user_id for copy in copies}
    assert people["helper"].id not in {copy.user_id for copy in copies}
    await cashier.press(f"sup:pay:{again.id}")
    await cashier.send("Yozib qo'ydim, ertaga hal bo'ladi.")
    assert cashier.last_text() == texts.SUPPORT_REPLY_SENT


async def test_moderators_copies_show_the_decision(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession
) -> None:
    from app.models.enums import ContributionKind
    from app.services import community

    people = await _people(db)
    await grant_permissions(db, people["helper"], Perm.COMMUNITY_MANAGE)
    item = await community.submit(
        db, people["member"], kind=ContributionKind.THOUGHT, text="Kitob o'qish — o'zingiz bilan suhbat."
    )
    await db.commit()
    key = f"contribution:{item.id}"
    copies = list(await db.scalars(select(Notification).where(Notification.sync_key == key)))
    assert {copy.user_id for copy in copies} == {people["boss"].id, people["helper"].id}
    await send_due_notifications(get_session_factory(), _bot(FakeTelegramSession()))

    # the boss decides in the Admin Panel: the helper's message in the bot says so
    decided = await client.post(
        f"/api/v1/admin/community/{item.id}/moderate", json={"action": "approve"}, headers=admin_headers(people["boss"])
    )
    assert decided.status_code == 200
    edits = list(await db.scalars(select(Notification).where(Notification.payload["edit_of"].is_not(None))))
    assert {edit.user_id for edit in edits} == {people["boss"].id, people["helper"].id}
    assert all("Lentaga chiqarildi</b> — Akmal Bosh" in edit.text for edit in edits)
    assert all(edit.payload["buttons"][0]["admin_route"] == "community" for edit in edits)

    # pressed in the bot: that message is changed by the button itself, the others by the queue
    helper = BotHarness(people["helper"].telegram_id)
    helper_copy = next(copy for copy in copies if copy.user_id == people["helper"].id)
    await db.refresh(helper_copy)
    message = Message(
        message_id=helper_copy.telegram_message_id,
        date=datetime.now(UTC),
        chat=Chat(id=people["helper"].telegram_id, type="private"),
        text="💬 Yangi fikr",
    )
    callback = CallbackQuery(
        id="1", from_user=helper.user, chat_instance="c", data=f"cm:hide:{item.id.hex}", message=message
    )
    await helper.dispatcher.feed_update(helper.bot, Update(update_id=next(_ids), callback_query=callback))
    hidden = list(
        await db.scalars(
            select(Notification).where(
                Notification.payload["edit_of"].is_not(None), Notification.text.like("%Yashirildi%")
            )
        )
    )
    assert [edit.user_id for edit in hidden] == [people["boss"].id]
