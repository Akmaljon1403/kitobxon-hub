"""Round K4: everything about money in one payments channel — and answered right there. An admin replies
(«Reply») in the channel to a payment question, a receipt or a payment line, and the words reach that
member; «✍️ Javob yozish» pressed in the channel works; Premium given by hand is written there too."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import SendMessage, SetMessageReaction
from aiogram.types import Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.models import Notification, PaymentsChatLink, SupportMessage, User
from app.models.enums import FeatureMode
from app.services import features, support
from app.services.settings import update_setting
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role
from tests.test_phase51_stars_orders import _buy_stars, _press_in_channel

_ids = itertools.count(3_100_000)
CHANNEL = -1004445556667


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> FakeTelegramSession:
    session = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)
    return session


async def _club(db: AsyncSession, chat: int = CHANNEL) -> dict[str, User]:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Bosh")
    member = await create_user(
        db, telegram_id=next(_ids), first_name="Nodir", last_name="Qodirov", telegram_username="nodir"
    )
    stranger = await create_user(db, telegram_id=next(_ids), first_name="Begona")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    for code in ("premium", "card_payments"):
        await features.set_mode(db, actor_id=boss.id, code=code, new_mode=FeatureMode.ALL, announce=False)
    await update_setting(db, key="payments.card_number", value="8600 0000 0000 0003", actor_id=boss.id)
    await update_setting(db, key="payments.star_price_uzs", value=230, actor_id=boss.id)
    await update_setting(db, key="payments.chat_id", value=str(chat), actor_id=boss.id)
    return {"boss": boss, "member": member, "stranger": stranger}


async def _reply(harness: BotHarness, *, chat: Chat, to: int, text: str, author: TgUser | None = None) -> None:
    """An admin's «Reply» in the payments channel (a channel post) or group (a message)."""
    original = Message(message_id=to, date=datetime.now(UTC), chat=chat, text="…")
    fields = {
        "message_id": next(_ids),
        "date": datetime.now(UTC),
        "chat": chat,
        "text": text,
        "reply_to_message": original,
    }
    if chat.type == "channel":
        update = Update(update_id=next(_ids), channel_post=Message(**fields))
    else:
        update = Update(update_id=next(_ids), message=Message(**fields, from_user=author or harness.user))
    await harness.dispatcher.feed_update(harness.bot, update)


async def _link(db: AsyncSession, kind: str) -> PaymentsChatLink:
    return await db.scalar(
        select(PaymentsChatLink).where(PaymentsChatLink.kind == kind).order_by(PaymentsChatLink.created_at.desc())
    )


async def test_answers_written_in_the_payments_channel(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession
) -> None:
    club = await _club(db)
    member = club["member"]
    channel = Chat(id=CHANNEL, type="channel", title="To'lovlar")

    # a payment question goes to the channel, with a hint how to answer it right there
    ticket = await support.member_message(db, user=member, text="Chekim tekshirildimi?", topic="payment")
    await db.commit()
    question = next(m for m in telegram.sent_messages() if "To'lov bo'yicha murojaat" in (m.text or ""))
    assert "«Reply»" in question.text
    link = await _link(db, "ticket")
    assert link.target_id == ticket.id and link.chat_id == CHANNEL

    admin = BotHarness(club["boss"].telegram_id)
    await _reply(admin, chat=channel, to=link.message_id, text="Ha, chekingiz tasdiqlandi. Rahmat!")
    answer = await db.scalar(select(SupportMessage).where(SupportMessage.from_admin.is_(True)))
    assert answer.text == "Ha, chekingiz tasdiqlandi. Rahmat!" and answer.ticket_id == ticket.id
    told = await db.scalar(select(Notification).where(Notification.dedup_key == f"support-reply:{answer.id}"))
    assert told.user_id == member.id and "Klub rahbariyatidan javob" in told.text
    assert any(isinstance(request, SetMessageReaction) for request in admin.session.requests)
    assert not any("↪️" in (m.text or "") for m in telegram.sent_messages())  # no copy: it is already there

    # a reply to a receipt goes to the member with what the payment was
    await _buy_stars(client, member)
    card = await _link(db, "card")
    await _reply(admin, chat=channel, to=card.message_id, text="Chekning to'liq rasmini yuboring, iltimos.")
    note = await db.scalar(
        select(Notification).where(Notification.user_id == member.id, Notification.text.like("%to'liq rasmini%"))
    )
    assert "to'lovingiz bo'yicha: ⭐ 100 Telegram Stars, 23 000 so'm" in note.text
    assert note.payload["buttons"][0]["callback"] == "sup:new:pay"

    # a reply to anything else, or without words, does nothing to members
    before = await db.scalar(select(Notification.id).order_by(Notification.created_at.desc()).limit(1))
    await _reply(admin, chat=channel, to=999_999, text="Shunchaki gap")
    after = await db.scalar(select(Notification.id).order_by(Notification.created_at.desc()).limit(1))
    assert before == after

    # «✍️ Javob yozish» pressed in the channel: the admin answers right there, with a «Reply»
    await _press_in_channel(admin, f"sup:pay:{ticket.id}")
    assert texts.SUPPORT_REPLY_CHANNEL_HINT in admin.session.alerts()

    # Premium given by hand is written in the channel too
    granted = await client.post(
        "/api/v1/admin/premium/grant",
        json={"user_id": str(member.id), "days": 30, "note": "Oktabr g'olibi"},
        headers=admin_headers(club["boss"]),
    )
    assert granted.status_code == 201
    line = next(m for m in telegram.sent_messages() if "Premium sovg'a" in (m.text or ""))
    assert "30 kun" in line.text and "Oktabr g'olibi" in line.text


async def test_in_a_payments_group_only_the_super_admins_answer(
    db: AsyncSession, telegram: FakeTelegramSession
) -> None:
    group_id = -1009998887776
    club = await _club(db, chat=group_id)
    group = Chat(id=group_id, type="supergroup", title="To'lovlar")
    await support.member_message(db, user=club["member"], text="Pulni qaytarasizmi?", topic="payment")
    await db.commit()
    link = await _link(db, "ticket")

    stranger = BotHarness(club["stranger"].telegram_id)
    await _reply(stranger, chat=group, to=link.message_id, text="Men javob beraman")
    assert texts.PAYCHAT_SUPER_ONLY in stranger.all_text()
    assert await db.scalar(select(SupportMessage).where(SupportMessage.from_admin.is_(True))) is None

    boss = BotHarness(club["boss"].telegram_id)
    await _reply(boss, chat=group, to=link.message_id, text="Ha, ertaga qaytaramiz.")
    answer = await db.scalar(select(SupportMessage).where(SupportMessage.from_admin.is_(True)))
    assert answer.text == "Ha, ertaga qaytaramiz." and answer.admin_id == club["boss"].id

    # an ordinary group message (not a reply) is still ignored, as before
    before = len(boss.session.requests)
    update = Update(
        update_id=next(_ids),
        message=Message(
            message_id=next(_ids), date=datetime.now(UTC), chat=group, from_user=boss.user, text="salom hammaga"
        ),
    )
    await boss.dispatcher.feed_update(boss.bot, update)
    assert len(boss.session.requests) == before
    assert not any(
        isinstance(request, SendMessage) and request.chat_id == group_id for request in boss.session.requests[before:]
    )
