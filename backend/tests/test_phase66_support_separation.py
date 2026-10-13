"""A general question and a money question from the same member are two separate conversations.

The bug this guards against: one account sent both a general and a payment message; the answer to the
payment one appeared under the general one too, and the admin who answered got swapped between them. Each
kind must keep its own ticket, its own copies and its own «who answered».
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import EditMessageText
from aiogram.types import CallbackQuery, Chat, Message, Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, PaymentsChatLink, SupportMessage, SupportTicket, User
from app.models.enums import SupportTicketKind, SupportTicketStatus
from app.security.permissions import Perm
from app.services import support
from app.services.settings import update_setting
from app.workers import sender as sender_module
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

sender_module.SEND_INTERVAL_SECONDS = 0
_ids = itertools.count(4_200_000)
CHANNEL = -1007778001122


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> FakeTelegramSession:
    session = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)
    return session


async def _people(db: AsyncSession) -> dict[str, User]:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmal", last_name="Bosh")
    helper = await create_user(db, telegram_id=next(_ids), first_name="Dilnoza", last_name="Aliyeva")
    cashier = await create_user(db, telegram_id=next(_ids), first_name="Sardor", last_name="Kassir")
    member = await create_user(db, telegram_id=next(_ids), first_name="Nodir", last_name="Qodirov")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await grant_role(db, helper, "ADMIN")
    await grant_role(db, cashier, "ADMIN")
    await grant_permissions(db, helper, Perm.SUPPORT_MANAGE)
    await grant_permissions(db, cashier, Perm.PAYMENT_SUPPORT)
    return {"boss": boss, "helper": helper, "cashier": cashier, "member": member}


async def _copies(db: AsyncSession, ticket_id: object) -> list[Notification]:
    return list(
        await db.scalars(
            select(Notification)
            .where(Notification.sync_key == f"ticket:{ticket_id}")
            .execution_options(populate_existing=True)
        )
    )


async def _channel_reply(harness: BotHarness, chat: Chat, to: int, text: str) -> None:
    original = Message(message_id=to, date=datetime.now(UTC), chat=chat, text="…")
    post = Message(message_id=next(_ids), date=datetime.now(UTC), chat=chat, text=text, reply_to_message=original)
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), channel_post=post))


async def _press(harness: BotHarness, data: str, chat: Chat, message_id: int) -> None:
    message = Message(message_id=message_id, date=datetime.now(UTC), chat=chat, text="💳 murojaat")
    callback = CallbackQuery(id=str(next(_ids)), from_user=harness.user, chat_instance="c", data=data, message=message)
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), callback_query=callback))


async def test_general_and_payment_stay_separate(db: AsyncSession, telegram: FakeTelegramSession) -> None:
    people = await _people(db)
    await update_setting(db, key="payments.chat_id", value=str(CHANNEL), actor_id=people["boss"].id)
    channel = Chat(id=CHANNEL, type="channel", title="To'lovlar")

    # the SAME member sends a general question and a money question
    general = await support.member_message(db, user=people["member"], text="Kitobni qachon topshiraman?")
    payment = await support.member_message(db, user=people["member"], text="Premium yoqilmadi", topic="payment")
    await db.commit()

    assert general.id != payment.id
    assert general.kind == SupportTicketKind.GENERAL and payment.kind == SupportTicketKind.PAYMENT

    link = await db.scalar(select(PaymentsChatLink).where(PaymentsChatLink.target_id == payment.id))
    assert link is not None  # only the payment one went to the payments channel

    # the cashier answers the PAYMENT question in the channel
    cashier = BotHarness(people["cashier"].telegram_id)
    await _press(cashier, f"sup:pay:{payment.id}", channel, link.message_id)
    await _channel_reply(cashier, channel, link.message_id, "Premium yoqildi.")

    pay_ticket = await db.get(SupportTicket, payment.id)
    gen_ticket = await db.get(SupportTicket, general.id)
    await db.refresh(pay_ticket)
    await db.refresh(gen_ticket)
    assert pay_ticket.status == SupportTicketStatus.ANSWERED
    assert gen_ticket.status == SupportTicketStatus.OPEN  # the general one is untouched

    # the answer belongs to the payment ticket only, by the cashier
    answers = list(await db.scalars(select(SupportMessage).where(SupportMessage.from_admin.is_(True))))
    assert len(answers) == 1
    assert answers[0].ticket_id == payment.id and answers[0].admin_id == people["cashier"].id

    # the general copies still say "waiting", never "answered" — no bleed-over
    for copy in await _copies(db, general.id):
        assert support.WAITING in copy.text and "Javob berildi" not in copy.text

    # now the helper answers the GENERAL question in the bot
    helper = BotHarness(people["helper"].telegram_id)
    await helper.press(f"sup:ans:{general.id}")
    await helper.send("Dushanba kuni topshirasiz.")

    gen_ticket = await db.get(SupportTicket, general.id)
    await db.refresh(gen_ticket)
    assert gen_ticket.status == SupportTicketStatus.ANSWERED
    gen_answer = await db.scalar(
        select(SupportMessage).where(SupportMessage.ticket_id == general.id, SupportMessage.from_admin.is_(True))
    )
    assert gen_answer.admin_id == people["helper"].id  # not swapped with the cashier

    # the payment channel message still credits the cashier, not the helper
    done = [r for r in telegram.requests if isinstance(r, EditMessageText) and "Javob berildi" in r.text]
    pay_done = [r for r in done if r.chat_id == CHANNEL]
    assert pay_done and "Sardor Kassir" in pay_done[-1].text and "Dilnoza" not in pay_done[-1].text


async def test_panel_shows_general_only_and_guards_payment(
    client: httpx.AsyncClient, db: AsyncSession, telegram: FakeTelegramSession
) -> None:
    people = await _people(db)
    payment = await support.member_message(db, user=people["member"], text="Chek yubordim", topic="payment")
    general = await support.member_message(db, user=people["member"], text="Oddiy savol")
    await db.commit()

    # the «Murojaatlar» panel lists the general question only — the payment one lives in the channel
    listed = await client.get("/api/v1/admin/support", headers=admin_headers(people["helper"]))
    ids = {row["id"] for row in listed.json()["items"]}
    assert str(general.id) in ids and str(payment.id) not in ids

    # a SUPPORT_MANAGE admin may answer the general one, but cannot open or answer the payment one
    ok = await client.post(
        f"/api/v1/admin/support/{general.id}/reply", json={"text": "Javob"}, headers=admin_headers(people["helper"])
    )
    assert ok.status_code == 200
    assert (
        await client.get(f"/api/v1/admin/support/{payment.id}", headers=admin_headers(people["helper"]))
    ).status_code == 403
    denied = await client.post(
        f"/api/v1/admin/support/{payment.id}/reply", json={"text": "Javob"}, headers=admin_headers(people["helper"])
    )
    assert denied.status_code == 403

    # the super admin may answer the payment one, and it is handled as a payment
    done = await client.post(
        f"/api/v1/admin/support/{payment.id}/reply", json={"text": "Tekshirdik"}, headers=admin_headers(people["boss"])
    )
    assert done.status_code == 200
    detail = await client.get(f"/api/v1/admin/support/{payment.id}", headers=admin_headers(people["boss"]))
    assert detail.json()["kind"] == "PAYMENT"
