"""Round I3: Stars bought with a bank card. The super admin confirms, the admin given «⭐ Stars yuborish»
gets the order in the bot and gifts the Stars, the member is told — and every step is written in the
payments channel, wherever it was taken. Money questions are a conversation between the member and the
super admins."""

from __future__ import annotations

import io
import itertools
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import EditMessageText, SendMessage, SendPhoto
from aiogram.types import CallbackQuery, Chat, Message, Update
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.models import CardPayment, Notification, User
from app.models.enums import CardPaymentStatus, FeatureMode, PaymentKind
from app.security.permissions import Perm
from app.services import card_payments, features, support
from app.services.settings import update_setting
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

_ids = itertools.count(2_300_000)
CHANNEL = -1004445556667


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> FakeTelegramSession:
    """What the services send (the payments channel posts)."""
    session = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)
    return session


def _channel(session: FakeTelegramSession) -> list[str]:
    return [m.text for m in session.sent_messages() if m.chat_id in (CHANNEL, str(CHANNEL))]


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (500, 800), (230, 230, 230)).save(buffer, format="JPEG")
    return buffer.getvalue()


async def _press_in_channel(harness: BotHarness, data: str) -> None:
    """A button under the receipt in the payments channel."""
    message = Message(
        message_id=next(_ids),
        date=datetime.now(UTC),
        chat=Chat(id=CHANNEL, type="channel", title="To'lovlar"),
        text="💳 Yangi karta to'lovi",
    )
    callback = CallbackQuery(id=str(next(_ids)), from_user=harness.user, chat_instance="c", data=data, message=message)
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), callback_query=callback))


async def _club(db: AsyncSession) -> dict[str, User]:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Bosh")
    sender = await create_user(db, telegram_id=next(_ids), first_name="Sardor", last_name="Stars")
    helper = await create_user(db, telegram_id=next(_ids), first_name="Yordamchi")
    member = await create_user(db, telegram_id=next(_ids), first_name="Nodir", telegram_username="nodir_reads")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await grant_role(db, sender, "ADMIN")
    await grant_permissions(db, sender, Perm.STARS_SEND)
    await grant_role(db, helper, "ADMIN")
    await grant_permissions(db, helper, Perm.SUPPORT_MANAGE)
    for code in ("premium", "card_payments"):
        await features.set_mode(db, actor_id=boss.id, code=code, new_mode=FeatureMode.ALL, announce=False)
    await update_setting(db, key="payments.card_number", value="8600 0000 0000 0003", actor_id=boss.id)
    await update_setting(db, key="payments.star_price_uzs", value=230, actor_id=boss.id)
    await update_setting(db, key="payments.chat_id", value=str(CHANNEL), actor_id=boss.id)
    return {"boss": boss, "sender": sender, "helper": helper, "member": member}


async def _buy_stars(client: httpx.AsyncClient, member: User, stars: int = 100) -> str:
    response = await client.post(
        "/api/v1/me/premium/card-payments",
        data={"stars": str(stars)},
        files={"file": ("chek.jpg", _jpeg(), "image/jpeg")},
        headers=member_headers(member),
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


async def _orders_for(db: AsyncSession, user: User) -> list[Notification]:
    return list(
        await db.scalars(
            select(Notification).where(Notification.user_id == user.id, Notification.dedup_key.like("stars-order:%"))
        )
    )


async def test_the_whole_stars_order_from_the_channel(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession
) -> None:
    club = await _club(db)
    payment_id = await _buy_stars(client, club["member"])
    receipts = [r for r in telegram.requests if isinstance(r, SendPhoto) and r.chat_id in (CHANNEL, str(CHANNEL))]
    assert len(receipts) == 1 and "100 Telegram Stars" in (receipts[0].caption or "")

    boss = BotHarness(club["boss"].telegram_id)
    await _press_in_channel(boss, f"cp:ok:{payment_id.replace('-', '')}")
    edited = next(r for r in reversed(boss.session.requests) if isinstance(r, EditMessageText))
    assert "Tasdiqlandi" in edited.text and "Yuborish topshirildi: Sardor Stars" in edited.text
    assert not any("Tasdiqlandi" in text for text in _channel(telegram))  # the receipt itself shows it: no copy

    # The order goes to the admin with «⭐ Stars yuborish» — not to the super admin who confirmed it.
    (order,) = await _orders_for(db, club["sender"])
    assert await _orders_for(db, club["boss"]) == []
    assert "Bosh admin tomonidan tasdiqlandi" in order.text and "Nodir" in order.text and "⭐ 100 Stars" in order.text
    assert "fragment.com" in order.text and order.payload["buttons"][0]["callback"].startswith("cp:sent:")

    # An admin without the right cannot mark it; the sender can (in the bot, privately).
    helper = BotHarness(club["helper"].telegram_id)
    await helper.press(order.payload["buttons"][0]["callback"])
    assert helper.session.alerts()[-1] == texts.STARS_SENDER_ONLY
    sender = BotHarness(club["sender"].telegram_id)
    await sender.press(order.payload["buttons"][0]["callback"])
    assert any("Stars yuborildi — Sardor" in r.text for r in sender.session.requests if isinstance(r, EditMessageText))
    assert any("⭐ <b>Stars yuborildi</b>" in text and "Yubordi: Sardor Stars" in text for text in _channel(telegram))
    told = await db.scalar(
        select(Notification.text).where(
            Notification.user_id == club["member"].id, Notification.dedup_key.like("%:delivered")
        )
    )
    assert "100 Stars sizga sovg'a qilindi" in told


async def test_admin_panel_steps_are_written_in_the_channel(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession
) -> None:
    club = await _club(db)
    first = await _buy_stars(client, club["member"])
    second = await _buy_stars(client, club["member"], 50)
    boss_headers = admin_headers(club["boss"])

    approved = await client.post(f"/api/v1/admin/premium/card-payments/{first}/approve", headers=boss_headers)
    assert approved.status_code == 200
    assert any("✅ <b>Tasdiqlandi</b>" in t and "Yuborish topshirildi: Sardor Stars" in t for t in _channel(telegram))
    rejected = await client.post(
        f"/api/v1/admin/premium/card-payments/{second}/reject", json={"reason": "Chek o'qilmaydi"}, headers=boss_headers
    )
    assert rejected.status_code == 200
    assert any("❌ <b>Rad etildi</b>" in t and "Chek o'qilmaydi" in t for t in _channel(telegram))

    # «⭐ Stars buyurtmalari» in the Admin Panel: for the sender, not for an admin without the right.
    forbidden = await client.get("/api/v1/admin/stars-orders", headers=admin_headers(club["helper"]))
    assert forbidden.status_code == 403
    listing = (await client.get("/api/v1/admin/stars-orders", headers=admin_headers(club["sender"]))).json()
    assert listing["waiting"] == 1 and listing["senders"] == "Sardor Stars"
    (item,) = listing["items"]
    assert (item["stars"], item["member_username"]) == (100, "nodir_reads") and item["approved_by"].startswith("Bosh")

    # Undo before the Stars are sent: the sender is told not to send them, the channel hears it.
    undone = await client.post(f"/api/v1/admin/premium/card-payments/{first}/undo", headers=boss_headers)
    assert undone.status_code == 200
    assert any("↩️ <b>Qaror qaytarildi</b>" in t for t in _channel(telegram))
    cancel = await db.scalar(
        select(Notification.text).where(
            Notification.user_id == club["sender"].id, Notification.dedup_key.like("stars-order-undo%")
        )
    )
    assert "Hozircha yubormang" in cancel

    await client.post(f"/api/v1/admin/premium/card-payments/{first}/approve", headers=boss_headers)
    assert len(await _orders_for(db, club["sender"])) == 2  # a fresh order after the new decision
    done = await client.post(f"/api/v1/admin/stars-orders/{first}/delivered", headers=admin_headers(club["sender"]))
    assert done.status_code == 200
    sent = (await client.get("/api/v1/admin/stars-orders?state=sent", headers=admin_headers(club["sender"]))).json()
    assert sent["waiting"] == 0 and sent["items"][0]["delivered_by"].startswith("Sardor")
    payment = await db.get(CardPayment, uuid.UUID(first))
    await db.refresh(payment)
    assert payment.status == CardPaymentStatus.APPROVED and payment.kind == PaymentKind.STARS
    assert payment.delivered_by == club["sender"].id


async def test_without_a_sender_the_super_admins_get_the_order(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession
) -> None:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Yolg'iz")
    member = await create_user(db, telegram_id=next(_ids), telegram_username="solo_reader")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    for code in ("premium", "card_payments"):
        await features.set_mode(db, actor_id=boss.id, code=code, new_mode=FeatureMode.ALL, announce=False)
    await update_setting(db, key="payments.card_number", value="8600 0000 0000 0004", actor_id=boss.id)
    payment_id = await _buy_stars(client, member)
    await client.post(f"/api/v1/admin/premium/card-payments/{payment_id}/approve", headers=admin_headers(boss))
    assert len(await _orders_for(db, boss)) == 1
    assert await card_payments.stars_sender_ids(db) == [boss.id]


async def test_stars_are_sent_automatically_when_a_provider_is_connected(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    club = await _club(db)
    calls: list[tuple[str, int, str]] = []

    async def fake_send(username: str, amount: int, *, idempotency_key: str) -> dict:
        calls.append((username, amount, idempotency_key))
        return {"request_id": "req-123"}

    monkeypatch.setattr("app.services.stars_provider.configured", lambda: True)
    monkeypatch.setattr("app.services.stars_provider.send_stars", fake_send)

    payment_id = await _buy_stars(client, club["member"])  # member @username is "nodir_reads"
    approved = await client.post(
        f"/api/v1/admin/premium/card-payments/{payment_id}/approve", headers=admin_headers(club["boss"])
    )
    assert approved.status_code == 200
    # The provider was asked once, for this member, with a stable idempotency key.
    # (The «@» is added inside the real send_stars; the caller passes the stored username.)
    assert calls == [("nodir_reads", 100, f"stars:{payment_id}")]
    payment = await db.get(CardPayment, uuid.UUID(payment_id))
    await db.refresh(payment)
    assert payment.delivered_at is not None and payment.delivered_by is None  # delivered by the provider, not an admin
    told = await db.scalar(
        select(Notification.text).where(
            Notification.user_id == club["member"].id, Notification.dedup_key.like("%:delivered")
        )
    )
    assert told is not None and "hisobingizga yuborildi" in told
    assert await _orders_for(db, club["sender"]) == []  # no manual order was raised
    listing = (await client.get("/api/v1/admin/stars-orders?state=sent", headers=admin_headers(club["sender"]))).json()
    assert listing["auto"] is True and listing["items"][0]["delivered_by"] is None


async def test_stars_fall_back_to_manual_when_the_provider_fails(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.stars_provider import StarsProviderError

    club = await _club(db)

    async def boom(username: str, amount: int, *, idempotency_key: str) -> dict:
        raise StarsProviderError("provayder rad etdi")

    monkeypatch.setattr("app.services.stars_provider.configured", lambda: True)
    monkeypatch.setattr("app.services.stars_provider.send_stars", boom)

    payment_id = await _buy_stars(client, club["member"])
    approved = await client.post(
        f"/api/v1/admin/premium/card-payments/{payment_id}/approve", headers=admin_headers(club["boss"])
    )
    assert approved.status_code == 200
    payment = await db.get(CardPayment, uuid.UUID(payment_id))
    await db.refresh(payment)
    assert payment.delivered_at is None  # not delivered — it waits for a manual gift
    assert len(await _orders_for(db, club["sender"])) == 1  # the manual order was raised instead


async def test_money_questions_are_answered_by_the_super_admin(db: AsyncSession, telegram: FakeTelegramSession) -> None:
    club = await _club(db)
    ticket = await support.member_message(db, user=club["member"], text="Stars qachon keladi?", topic="payment")
    await db.commit()
    assert any("Stars qachon keladi?" in text for text in _channel(telegram))

    helper = BotHarness(club["helper"].telegram_id)
    await helper.press(f"sup:pay:{ticket.id}")
    assert helper.session.alerts()[-1] == texts.SUPPORT_PAYMENT_NO_RIGHT  # no «💳 To'lov savollari» right

    boss = BotHarness(club["boss"].telegram_id)
    await boss.press(f"sup:pay:{ticket.id}")
    await boss.send("Bugun kechgacha yuboriladi")
    answer = await db.scalar(
        select(Notification).where(
            Notification.user_id == club["member"].id, Notification.dedup_key.like("support-reply:%")
        )
    )
    assert "Bugun kechgacha" in answer.text and answer.payload["buttons"][0]["callback"] == "sup:new:pay"
    assert any("↪️ <b>Javob</b>" in t and "Bugun kechgacha yuboriladi" in t for t in _channel(telegram))
    assert not any(isinstance(r, SendMessage) and r.chat_id == CHANNEL for r in boss.session.requests)
