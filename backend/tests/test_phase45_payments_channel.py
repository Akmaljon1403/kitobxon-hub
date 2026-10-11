"""Round G1: everything about money goes to the payments channel, and the bot asks the owners what a
channel is for as soon as it is made an administrator there."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import GetChat, GetChatMember, SendMessage
from aiogram.methods.base import TelegramMethod
from aiogram.types import AcceptedGiftTypes, ChatFullInfo, ChatMemberAdministrator, Update
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.models import CardPayment, Notification, Payment
from app.models.enums import CardPaymentStatus, PaymentKind, PaymentStatus
from app.security.permissions import Perm
from app.services import payments_chat, support
from app.services.settings import get_setting, update_setting
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

_ids = itertools.count(2_100_000)
CHANNEL = -1001234567890


class ChannelSession(FakeTelegramSession):
    """Also answers «what is this chat» and «is the bot an admin there»."""

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, GetChat):
            self.requests.append(method)
            return ChatFullInfo.model_validate(
                {
                    "id": CHANNEL,
                    "type": "channel",
                    "title": "Kitobxon to'lovlar",
                    "accent_color_id": 0,
                    "max_reaction_count": 11,
                    "accepted_gift_types": dict.fromkeys(_required(AcceptedGiftTypes), False),
                }
            )
        if isinstance(method, GetChatMember):
            self.requests.append(method)
            return ChatMemberAdministrator.model_validate({"user": BOT_USER, **_admin_rights()})
        return await super().make_request(bot, method, timeout)


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> ChannelSession:
    session = ChannelSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)
    return session


def _to_channel(session: FakeTelegramSession) -> list[SendMessage]:
    return [m for m in session.sent_messages() if m.chat_id in (CHANNEL, str(CHANNEL))]


async def test_payment_questions_only_in_the_payments_channel(db: AsyncSession, telegram: ChannelSession) -> None:
    member = await create_user(db)
    helper = await create_user(db)
    boss = await create_user(db)
    await db.commit()
    await grant_role(db, helper, "ADMIN")
    await grant_permissions(db, helper, Perm.SUPPORT_MANAGE)
    await grant_role(db, boss, "SUPER_ADMIN")

    def count(user_id: Any) -> Any:
        return db.scalar(select(func.count()).where(Notification.user_id == user_id))

    # Without a payments channel a money question goes to the super admins only (their conversation).
    await support.member_message(db, user=member, text="Chekim tasdiqlanmadi", topic="payment")
    await db.commit()
    assert (await count(boss.id), await count(helper.id)) == (1, 0)
    question = await db.scalar(select(Notification).where(Notification.user_id == boss.id))
    assert question.payload["buttons"][0]["callback"].startswith("sup:pay:")

    await update_setting(db, key="payments.chat_id", value=str(CHANNEL), actor_id=None)
    await support.member_message(db, user=member, text="Yana bir savol", topic="payment")
    await db.commit()
    posted = _to_channel(telegram)
    assert len(posted) == 1 and "Yana bir savol" in posted[0].text and "To'lov bo'yicha murojaat" in posted[0].text
    assert (await count(boss.id), await count(helper.id)) == (1, 0)  # no new private message
    # Other questions still go to the admins who answer questions.
    await support.member_message(db, user=member, text="Tadbir qachon?", topic="general")
    await db.commit()
    assert await count(helper.id) == 1


async def test_stars_payments_and_the_weekly_summary(db: AsyncSession, telegram: ChannelSession) -> None:
    from app.utils.timezone import local_tz

    member = await create_user(db, first_name="Aziza", last_name="Karimova", telegram_username="aziza")
    await db.commit()
    await update_setting(db, key="payments.chat_id", value=str(CHANNEL), actor_id=None)
    payment = Payment(
        user_id=member.id,
        kind=PaymentKind.DONATION,
        status=PaymentStatus.PAID,
        amount=50,
        invoice_payload="donation:50:x",
        telegram_charge_id=f"charge-{next(_ids)}",
    )
    db.add(payment)
    db.add(
        CardPayment(
            user_id=member.id,
            kind=PaymentKind.PREMIUM,
            amount_uzs=30000,
            receipt_key="r.jpg",
            status=CardPaymentStatus.APPROVED,
            decided_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db.commit()
    assert await payments_chat.stars_payment(db, payment, member)
    line = _to_channel(telegram)[-1].text
    assert "Telegram Stars to'lovi" in line and "@aziza" in line and "50 ⭐" in line and "Klubga hissa" in line

    today = datetime.now(local_tz())
    now = (today + timedelta(days=7 - today.weekday())).replace(hour=9, minute=5)  # next Monday, 09:05
    text = await payments_chat.summary_text(db, now - timedelta(days=30), now)
    assert "30 000 so'm" in text and "50 ⭐" in text
    assert await payments_chat.weekly_summary(db, now) == 1
    assert "Moliyaviy xulosa" in _to_channel(telegram)[-1].text
    assert await payments_chat.weekly_summary(db, now) == 0  # once a week
    assert await payments_chat.weekly_summary(db, now + timedelta(days=1)) == 0  # only on Mondays


BOT_USER = {"id": 123456789, "is_bot": True, "first_name": "Kitobxon"}


def _required(model: type[Any]) -> list[str]:
    """Fields the current Bot API asks for, so these fakes keep up with aiogram updates."""
    return [name for name, field in model.model_fields.items() if field.is_required()]


def _admin_rights() -> dict[str, Any]:
    rights = {name: True for name in _required(ChatMemberAdministrator) if name not in ("user", "status")}
    return {
        **rights,
        "status": "administrator",
        "can_be_edited": False,
        "is_anonymous": False,
        "can_post_messages": True,
    }


def _promotion(admin_id: int, new: str = "administrator") -> Update:
    admin = {"user": BOT_USER, **_admin_rights()}
    left = {"user": BOT_USER, "status": new if new != "administrator" else "left"}
    return Update.model_validate(
        {
            "update_id": next(_ids),
            "my_chat_member": {
                "chat": {"id": CHANNEL, "type": "channel", "title": "Kitobxon to'lovlar"},
                "from": {"id": admin_id, "is_bot": False, "first_name": "Akmal"},
                "date": int(datetime.now(UTC).timestamp()),
                "old_chat_member": left if new == "administrator" else admin,
                "new_chat_member": admin if new == "administrator" else left,
            },
        }
    )


async def test_adding_the_bot_to_a_channel_asks_the_owners(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = await create_user(db, telegram_id=next(_ids))
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, owner, "SUPER_ADMIN")

    harness = BotHarness(owner.telegram_id)
    harness.bot.session = ChannelSession()  # the bot can look at the channel
    harness.session = harness.bot.session  # type: ignore[assignment]
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: harness.bot)
    await harness.dispatcher.feed_update(harness.bot, _promotion(owner.telegram_id))
    asked = await db.scalar(select(Notification).where(Notification.user_id == owner.id))
    assert asked is not None and "Kitobxon to'lovlar" in asked.text
    callbacks = [button["callback"] for button in asked.payload["buttons"]]
    assert callbacks == [f"chatrole:pay:{CHANNEL}", f"chatrole:club:{CHANNEL}", f"chatrole:none:{CHANNEL}"]
    assert await db.scalar(select(func.count()).where(Notification.user_id == member.id)) == 0

    other = BotHarness(member.telegram_id)
    await other.press(f"chatrole:pay:{CHANNEL}")
    assert other.session.alerts()[-1] == texts.CARD_ADMIN_ONLY
    assert await get_setting(db, "payments.chat_id") == ""

    owner_id, owner_tg = owner.id, owner.telegram_id
    await harness.press(f"chatrole:pay:{CHANNEL}")
    db.expire_all()
    assert await get_setting(db, "payments.chat_id") == str(CHANNEL)
    assert "Sinov xabari" in _to_channel(harness.session)[-1].text

    # Removed from the payments channel: the owners are told.
    await harness.dispatcher.feed_update(harness.bot, _promotion(owner_tg, new="left"))
    lost = await db.scalar(select(Notification).where(Notification.dedup_key.like(f"chat-lost:{CHANNEL}:%")))
    assert lost is not None and lost.user_id == owner_id


async def test_the_payments_channel_in_the_admin_panel(
    client: httpx.AsyncClient, db: AsyncSession, telegram: ChannelSession
) -> None:
    owner = await create_user(db)
    await db.commit()
    await grant_role(db, owner, "SUPER_ADMIN")
    headers = admin_headers(owner)
    assert (await client.get("/api/v1/admin/premium/payments-chat", headers=headers)).json()["chat_id"] is None
    await update_setting(db, key="payments.chat_id", value=str(CHANNEL), actor_id=None)
    status = (await client.get("/api/v1/admin/premium/payments-chat", headers=headers)).json()
    assert status == {"chat_id": str(CHANNEL), "title": "Kitobxon to'lovlar", "ok": True, "problem": None}
    sent = (await client.post("/api/v1/admin/premium/payments-chat/test", headers=headers)).json()
    assert sent["sent"] is True and "Sinov xabari" in _to_channel(telegram)[-1].text
    summary = (await client.get("/api/v1/admin/premium/money-summary", headers=headers)).json()
    assert "Moliyaviy xulosa" in summary["text"]
