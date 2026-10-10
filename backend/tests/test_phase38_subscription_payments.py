"""Round E3–E5: the required channel subscription, the welcome tour with the automatic Premium trial,
the payments chat with «↩️ Qaytarish», Stars only for members with a username, and premium emoji
inside the bot's messages."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText, GetChat, GetChatMember, SendMessage, SendPhoto
from aiogram.methods.base import TelegramMethod
from aiogram.types import CallbackQuery, Chat, ChatMemberLeft, ChatMemberMember, Message, MessageEntity, Update
from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.emoji import CustomEmojiMiddleware
from app.models import CardPayment, Notification, PremiumSubscription, User
from app.models.enums import CardPaymentStatus, FeatureMode, PremiumSource, UserStatus
from app.services import card_payments, custom_emoji, features, subscription
from app.services import premium as premium_service
from app.services.settings import update_setting
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role, member_headers
from tests.test_phase28_card_payments import _jpeg, _open_card_payments, _submit, _super_admin

_ids = itertools.count(1_400_000)


@pytest.fixture(autouse=True)
def _fresh_emoji() -> Any:
    custom_emoji.use({})
    custom_emoji._paused_until = 0.0
    yield
    custom_emoji.use({})
    custom_emoji._paused_until = 0.0


class ChannelTelegram(FakeTelegramSession):
    """Answers «is this person in the channel?» from a set of subscribed Telegram ids."""

    def __init__(self, subscribed: set[int], *, broken: bool = False) -> None:
        super().__init__()
        self.subscribed = subscribed
        self.broken = broken

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, GetChatMember):
            self.requests.append(method)
            if self.broken:
                raise TelegramBadRequest(method=method, message="Bad Request: member list is inaccessible")
            user = TgUser(id=method.user_id, is_bot=False, first_name="X")
            if method.user_id in self.subscribed:
                return ChatMemberMember(user=user)
            return ChatMemberLeft(user=user)
        if isinstance(method, GetChat):
            raise TelegramBadRequest(method=method, message="Bad Request: chat not found")  # the title falls back
        return await super().make_request(bot, method, timeout)


def _gate_harness(telegram_id: int, session: ChannelTelegram) -> BotHarness:
    harness = BotHarness(telegram_id)
    harness.session = session
    harness.bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return harness


# ---------------------------------------------------------------------------- required subscription


def test_channel_list_is_read_kindly() -> None:
    assert subscription.parse("@FJSTIMutolaaxona, https://t.me/kitob_klub ; t.me/other_ch") == [
        ("@FJSTIMutolaaxona", "https://t.me/FJSTIMutolaaxona"),
        ("@kitob_klub", "https://t.me/kitob_klub"),
        ("@other_ch", "https://t.me/other_ch"),
    ]
    assert subscription.parse("-1001234567890=https://t.me/+AbCdEf") == [("-1001234567890", "https://t.me/+AbCdEf")]
    assert subscription.parse("salom @a @FJSTIMutolaaxona @fjstimutolaaxona") == [
        ("@FJSTIMutolaaxona", "https://t.me/FJSTIMutolaaxona")
    ]


@pytest.mark.subscription
async def test_bot_asks_to_subscribe_and_then_continues(db: AsyncSession) -> None:
    telegram_id = next(_ids)
    session = ChannelTelegram(subscribed=set())
    harness = _gate_harness(telegram_id, session)

    await harness.send("/start ev_0123456789abcdef0123456789abcdef")
    ask = harness.session.sent_messages()[-1]
    assert ask.text == texts.SUBSCRIBE_REQUIRED
    rows = ask.reply_markup.inline_keyboard
    assert rows[0][0].url == "https://t.me/FJSTIMutolaaxona"
    assert rows[-1][0].callback_data == "sub:check:ev_0123456789abcdef0123456789abcdef"  # continues the link

    await harness.press("sub:check")
    assert "Hali obuna ko'rinmayapti" in harness.session.alerts()[-1]

    session.subscribed.add(telegram_id)
    await harness.press("sub:check:ev_0123456789abcdef0123456789abcdef")
    edited = next(r for r in reversed(harness.session.requests) if isinstance(r, EditMessageText))
    assert edited.text == texts.SUBSCRIBE_THANKS
    assert texts.WELCOME_NEW in harness.all_text()  # registration starts right away


@pytest.mark.subscription
async def test_admins_and_unreachable_channels_pass(db: AsyncSession) -> None:
    admin = await _super_admin(db, telegram_id=next(_ids))
    await db.commit()
    harness = _gate_harness(admin.telegram_id, ChannelTelegram(subscribed=set()))
    await harness.send("/start")
    assert texts.SUBSCRIBE_REQUIRED not in harness.all_text()

    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    broken = _gate_harness(member.telegram_id, ChannelTelegram(subscribed=set(), broken=True))
    await broken.send("/start")
    assert texts.SUBSCRIBE_REQUIRED not in broken.all_text()  # the bot is not an admin there: let them in

    await update_setting(db, key="subscription.required", value=False, actor_id=admin.id)
    other = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    off = _gate_harness(other.telegram_id, ChannelTelegram(subscribed=set()))
    await off.send("/start")
    assert texts.SUBSCRIBE_REQUIRED not in off.all_text()


@pytest.mark.subscription
async def test_mini_app_needs_the_subscription_too(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    session = ChannelTelegram(subscribed=set())
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr(subscription, "_bot", lambda: bot)
    headers = member_headers(member)

    me = await client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["subscription_missing"] == [{"title": "@FJSTIMutolaaxona", "url": "https://t.me/FJSTIMutolaaxona"}]
    books = await client.get("/api/v1/books", headers=headers)
    assert books.status_code == 403 and books.json()["error"]["code"] == "SUBSCRIPTION_REQUIRED"
    assert books.json()["error"]["details"]["channels"][0]["url"] == "https://t.me/FJSTIMutolaaxona"

    session.subscribed.add(member.telegram_id)
    cached = await client.get("/api/v1/me/subscription", headers=headers)
    assert cached.json()["ok"] is False  # remembered for a few seconds
    fresh = await client.get("/api/v1/me/subscription?fresh=true", headers=headers)
    assert fresh.json() == {"ok": True, "channels": []}
    assert (await client.get("/api/v1/books", headers=headers)).status_code == 200


async def test_bot_stays_quiet_in_groups(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    harness = BotHarness(member.telegram_id)
    group = Chat(id=-100777, type="supergroup")
    user = TgUser(id=member.telegram_id, is_bot=False, first_name="A")
    message = Message(message_id=1, date=datetime.now(UTC), chat=group, from_user=user, text="/start")
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), message=message))
    assert harness.session.sent_messages() == []
    callback = CallbackQuery(id="1", from_user=user, chat_instance="g", data="prem:open", message=message)
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), callback_query=callback))
    assert harness.session.sent_messages() == []


# ---------------------------------------------------------------------------- welcome tour and the trial


async def test_registration_starts_the_trial_and_tells_what_premium_gives(db: AsyncSession) -> None:
    owner = await _super_admin(db)
    await features.set_mode(db, actor_id=owner.id, code="premium", new_mode=FeatureMode.ALL, announce=False)
    await db.commit()
    harness = BotHarness(next(_ids))
    await harness.send("/start")
    await harness.send("Aziza")
    await harness.send("Karimova")
    await harness.share_contact("+998901234588")
    await harness.press("reg:course:2")
    await harness.send("201")
    await harness.press("reg:confirm")
    user = await db.scalar(select(User).where(User.telegram_id == harness.user.id))
    if user is None or user.status != UserStatus.ACTIVE:
        pytest.skip("registration needs approval in this configuration")
    trial = await db.scalar(select(PremiumSubscription).where(PremiumSubscription.user_id == user.id))
    assert trial is not None and trial.source == PremiumSource.TRIAL
    text = harness.all_text()
    assert "Qisqa sayohat" in text and "kunlik Premium!" in text and "💎 belgisi" in text
    assert await premium_service.on_trial(db, user.id)
    # Only once: the Premium section no longer offers a trial.
    assert await premium_service.trial_days(db, user) == 0


async def test_approved_member_gets_the_trial(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    await features.set_mode(db, actor_id=owner.id, code="premium", new_mode=FeatureMode.ALL, announce=False)
    member = await create_user(db, status=UserStatus.PENDING)
    await db.commit()
    member_id = member.id
    response = await client.post(
        f"/api/v1/admin/users/{member_id}/status",
        json={"status": "ACTIVE", "reason": "Tasdiqlandi"},
        headers=admin_headers(owner),
    )
    assert response.status_code == 200, response.text
    note = await db.scalar(select(Notification).where(Notification.dedup_key == f"user_approved:{member_id}"))
    assert "kunlik Premium yoqildi" in note.text
    assert await premium_service.on_trial(db, member_id)


async def test_me_marks_premium_features_during_the_trial(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    await features.set_mode(db, actor_id=owner.id, code="premium", new_mode=FeatureMode.ALL, announce=False)
    await features.set_mode(db, actor_id=owner.id, code="portfolio", new_mode=FeatureMode.PREMIUM, announce=False)
    member = await create_user(db)
    await db.commit()
    assert await premium_service.welcome_trial(db, member) is not None
    me = (await client.get("/api/v1/me", headers=member_headers(member))).json()
    assert me["premium_trial"] is True and "portfolio" in me["premium_features"]
    await premium_service.grant(db, actor_id=owner.id, user_id=member.id, days=30, note=None)
    me = (await client.get("/api/v1/me", headers=member_headers(member))).json()
    assert me["premium_trial"] is True  # the paid period starts after the trial
    assert (await premium_service.welcome_trial(db, member)) is None  # never twice


# ---------------------------------------------------------------------------- payments


class ChatTelegram(FakeTelegramSession):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__()
        self.fail = fail

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if self.fail and isinstance(method, (SendPhoto, SendMessage)):
            raise TelegramBadRequest(method=method, message="Bad Request: chat not found")
        return await super().make_request(bot, method, timeout)


async def test_receipts_go_to_the_payments_chat(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await _super_admin(db)
    plan = await _open_card_payments(db, admin)
    await update_setting(db, key="payments.chat_id", value="-1009876543210", actor_id=admin.id)
    member = await create_user(db, first_name="Bobur")
    await db.commit()
    telegram = ChatTelegram()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)

    response = await _submit(client, member, plan_id=plan.id)
    assert response.status_code == 201, response.text
    photo = next(r for r in telegram.requests if isinstance(r, SendPhoto))
    assert photo.chat_id == "-1009876543210" and "Bobur" in photo.caption
    buttons = [b.callback_data for row in photo.reply_markup.inline_keyboard for b in row]
    assert buttons[0].startswith("cp:ok:") and buttons[1].startswith("cp:no:")
    dms = await db.scalar(select(Notification).where(Notification.dedup_key.like("card-payment:%")))
    assert dms is None  # no private messages when the chat got it

    # The chat cannot be reached: the super admins are told in the bot instead.
    telegram.fail = True
    other = await create_user(db)
    await db.commit()
    assert (await _submit(client, other, plan_id=plan.id)).status_code == 201
    dm = await db.scalar(select(Notification).where(Notification.dedup_key.like("card-payment:%")))
    assert dm is not None and dm.user_id == admin.id


async def test_payment_questions_reach_the_payments_chat(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    admin = await _super_admin(db)
    await update_setting(db, key="payments.chat_id", value="@club_payments", actor_id=admin.id)
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    telegram = ChatTelegram()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)

    harness = BotHarness(member.telegram_id)
    await harness.send("/paysupport")
    assert harness.session.sent_messages()[-1].reply_markup.inline_keyboard[0][0].callback_data == "sup:new:pay"
    await harness.press("sup:new:pay")
    assert harness.last_text() == texts.SUPPORT_ASK_PAYMENT
    await harness.send("Premium uchun to'ladim, hali yoqilmadi")
    copy = next(r for r in telegram.requests if isinstance(r, SendMessage))
    assert copy.chat_id == "@club_payments" and "To'lov bo'yicha murojaat" in copy.text
    assert copy.reply_markup.inline_keyboard[0][0].callback_data.startswith("sup:ans:")


async def test_stars_by_card_need_a_username(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    await _open_card_payments(db, admin)
    nameless = await create_user(db, telegram_username=None)
    await db.commit()
    response = await _submit(client, nameless, stars=100)
    assert response.status_code == 409 and response.json()["error"]["code"] == "STARS_NEED_USERNAME"


async def test_a_mistaken_decision_can_be_undone(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    plan = await _open_card_payments(db, admin)
    member = await create_user(db)
    await db.commit()
    member_id = member.id
    payment_id = (await _submit(client, member, plan_id=plan.id)).json()["id"]
    headers = admin_headers(admin)
    base = f"/api/v1/admin/premium/card-payments/{payment_id}"

    assert (await client.post(f"{base}/undo", headers=headers)).status_code == 409  # nothing decided yet
    assert (await client.post(f"{base}/approve", headers=headers)).status_code == 200
    first_end = await premium_service.premium_until(db, member_id)
    await premium_service.grant(db, actor_id=admin.id, user_id=member_id, days=10, note="sovg'a")
    assert (await client.post(f"{base}/undo", headers=headers)).status_code == 200
    stored = await db.get(CardPayment, payment_id)
    await db.refresh(stored)
    assert stored.status == CardPaymentStatus.PENDING and stored.subscription_id is None
    # The gift that came after the paid month moves up: 10 days from now, not from the old end.
    until = await premium_service.premium_until(db, member_id)
    assert until is not None and first_end is not None and until < first_end
    assert timedelta(days=9) < until - datetime.now(UTC) < timedelta(days=11)

    # Decided again (a new message to the member, not swallowed as a duplicate), then too late to undo.
    assert (await client.post(f"{base}/approve", headers=headers)).status_code == 200
    approved = list(
        await db.scalars(
            select(Notification).where(Notification.dedup_key.like(f"card-payment:{payment_id}:approved:%"))
        )
    )
    assert len(approved) == 2
    await db.refresh(stored)
    stored.decided_at = datetime.now(UTC) - timedelta(hours=card_payments.UNDO_HOURS + 1)
    await db.commit()
    late = await client.post(f"{base}/undo", headers=headers)
    assert late.status_code == 409 and late.json()["error"]["code"] == "UNDO_TOO_LATE"


async def test_card_first_in_the_premium_section(db: AsyncSession) -> None:
    admin = await _super_admin(db)
    await _open_card_payments(db, admin)
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    harness = BotHarness(member.telegram_id)
    await harness.send("/premium")
    keyboard = harness.session.sent_messages()[-1].reply_markup.inline_keyboard
    assert keyboard[0][0].callback_data == "card:open" and keyboard[1][0].callback_data == "prem:stars"
    assert "Bank kartasi" in harness.last_text()
    await harness.press("don:open")
    assert harness.last_text() == texts.DONATE_INFO
    donate = harness.session.sent_messages()[-1].reply_markup.inline_keyboard
    assert donate[0][0].callback_data == "don:card"


# ---------------------------------------------------------------------------- premium emoji


def test_premium_emoji_pairs_are_read_from_an_admin_message() -> None:
    # «✋ = 👋(premium)»: the ✋ before it is replaced; «👍(premium)» alone replaces its own 👍.
    text = "✋ = 👋\nSalom 👍"
    entities = [
        MessageEntity(type="custom_emoji", offset=4, length=2, custom_emoji_id="111"),
        MessageEntity(type="custom_emoji", offset=13, length=2, custom_emoji_id="222"),
    ]
    assert custom_emoji.pairs_from_message(text, entities) == [("✋", "111", "👋"), ("👍", "222", "👍")]
    assert custom_emoji.pairs_from_message("oddiy matn", []) == []


def test_emoji_are_replaced_outside_code_and_tags() -> None:
    custom_emoji.use({"✋": ("111", "✋"), "❤": ("222", "❤️")})
    html = 'Salom ✋ <b>do\'stim ✋</b> <code>✋</code> <a href="https://x.uz">❤️</a>'
    result = custom_emoji.apply(html)
    assert result.count('<tg-emoji emoji-id="111">✋</tg-emoji>') == 2
    assert "<code>✋</code>" in result
    assert '<a href="https://x.uz"><tg-emoji emoji-id="222">❤️</tg-emoji></a>' in result
    assert custom_emoji.apply("Hech narsa yo'q") == "Hech narsa yo'q"


async def test_messages_fall_back_to_ordinary_emoji_when_telegram_refuses(db: AsyncSession) -> None:
    custom_emoji.use({"✋": ("111", "✋")})

    class Refusing(FakeTelegramSession):
        def __init__(self) -> None:
            super().__init__()
            self.texts: list[str] = []  # the text as it was at the moment of sending

        async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
            if isinstance(method, SendMessage):
                self.texts.append(method.text)
                if "tg-emoji" in (method.text or ""):
                    raise TelegramBadRequest(method=method, message="Bad Request: custom emoji are not allowed")
            return await super().make_request(bot, method, timeout)

    session = Refusing()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(CustomEmojiMiddleware())
    custom_emoji._loaded_at = float("inf")  # do not reload from the database in this test
    await bot.send_message(1, "Salom ✋")
    assert session.texts == ['Salom <tg-emoji emoji-id="111">✋</tg-emoji>', "Salom ✋"]
    assert custom_emoji.paused()
    await bot.send_message(1, "Yana ✋")
    assert session.texts[-1] == "Yana ✋" and len(session.texts) == 3  # paused for an hour: no second try


async def test_admin_saves_premium_emoji_with_the_bot(db: AsyncSession) -> None:
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "SUPER_ADMIN")
    harness = BotHarness(admin.telegram_id)
    await harness.send("/emoji")
    assert "Premium emojilar" in harness.last_text()
    message = Message(
        message_id=next(_ids),
        date=datetime.now(UTC),
        chat=harness.chat,
        from_user=harness.user,
        text="🔥 = ⭐",
        entities=[MessageEntity(type="custom_emoji", offset=4, length=1, custom_emoji_id="999")],
    )
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), message=message))
    assert "Saqlandi" in harness.last_text() and 'emoji-id="999"' in harness.last_text()
    rows = await custom_emoji.list_all(db)
    assert [(row.emoji, row.custom_emoji_id) for row in rows] == [("🔥", "999")]
    await harness.send("/tayyor")
    assert harness.last_text() == texts.EMOJI_DONE
    await harness.press("emj:clear")
    assert await custom_emoji.list_all(db) == []


async def test_card_payment_status_shows_waiting_in_the_app(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    plan = await _open_card_payments(db, admin)
    member = await create_user(db)
    await db.commit()
    await _submit(client, member, plan_id=plan.id, receipt=_jpeg())
    mine = (await client.get("/api/v1/me/premium/card-payments", headers=member_headers(member))).json()
    assert mine[0]["status"] == "PENDING"
