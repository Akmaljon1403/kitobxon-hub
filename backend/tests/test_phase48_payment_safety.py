"""Round G4: money safety — the same receipt sent twice is flagged, and forgotten receipts are
recalled in the payments channel (not in the owners' private chats)."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import CardPayment, Notification
from app.models.enums import CardPaymentStatus, FeatureMode, NotificationType, PaymentKind
from app.services import admin_digest, features, payments_chat
from app.services.settings import update_setting
from app.utils.timezone import local_tz
from tests.bot_helpers import BOT_TOKEN, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role, member_headers

CHANNEL = -1009876543210


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> FakeTelegramSession:
    session = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)
    return session


def _jpeg(shade: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 1000), (shade, shade, shade)).save(buffer, format="JPEG")
    return buffer.getvalue()


async def test_the_same_receipt_twice_is_flagged(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await create_user(db)
    first = await create_user(db, first_name="Dilnoza", last_name="Yusupova")
    second = await create_user(db, first_name="Bekzod", last_name="Rahimov")
    await db.commit()
    await grant_role(db, owner, "SUPER_ADMIN")
    for code in ("premium", "card_payments"):
        await features.set_mode(db, actor_id=owner.id, code=code, new_mode=FeatureMode.ALL, announce=False)
    await update_setting(db, key="payments.card_number", value="8600 1234 5678 9012", actor_id=owner.id)

    async def submit(member, receipt: bytes) -> str:
        response = await client.post(
            "/api/v1/me/premium/card-payments",
            data={"amount_uzs": "20000"},
            files={"file": ("chek.jpg", receipt, "image/jpeg")},
            headers=member_headers(member),
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    await submit(first, _jpeg(200))
    await submit(second, _jpeg(120))  # another receipt: no warning
    copied = await submit(second, _jpeg(200))  # the first member's receipt again
    notes = list(
        await db.scalars(
            select(Notification.text)
            .where(Notification.user_id == owner.id, Notification.type == NotificationType.PREMIUM)
            .order_by(Notification.created_at)
        )
    )
    assert len(notes) == 3
    assert "avval ham yuborilgan" not in notes[0] and "avval ham yuborilgan" not in notes[1]
    assert "avval ham yuborilgan" in notes[2] and "Yusupova Dilnoza" in notes[2] and "20 000 so'm" in notes[2]

    listed = (await client.get("/api/v1/admin/premium/card-payments", headers=admin_headers(owner))).json()["items"]
    flags = {item["id"]: item["duplicate"] for item in listed}
    assert flags[copied] is True and sum(flags.values()) == 2


async def test_forgotten_receipts_are_recalled_in_the_channel(db: AsyncSession, telegram: FakeTelegramSession) -> None:
    member = await create_user(db)
    owner = await create_user(db)
    await db.commit()
    await grant_role(db, owner, "SUPER_ADMIN")
    today = datetime.now(local_tz())
    ten = today.replace(hour=10, minute=5, second=0, microsecond=0).astimezone(UTC)
    db.add(
        CardPayment(
            user_id=member.id,
            kind=PaymentKind.DONATION,
            amount_uzs=15000,
            receipt_key="r.jpg",
            status=CardPaymentStatus.PENDING,
            created_at=ten - timedelta(hours=5),
        )
    )
    await db.commit()

    assert await payments_chat.remind_pending(db, ten) == 0  # no payments channel: the morning digest tells
    assert "Tekshirilmagan to'lov cheklari" in await admin_digest.text(db, ten)

    await update_setting(db, key="payments.chat_id", value=str(CHANNEL), actor_id=None)
    assert await payments_chat.remind_pending(db, ten) == 1
    posted = telegram.sent_messages()[-1]
    assert posted.chat_id in (CHANNEL, str(CHANNEL)) and "Tekshirilmagan cheklar: 1" in posted.text
    assert "5 soatdan beri" in posted.text
    assert await payments_chat.remind_pending(db, ten + timedelta(minutes=20)) == 0  # once per slot
    assert await payments_chat.remind_pending(db, ten + timedelta(hours=2)) == 0  # only at 10:00 and 17:00
    # The owners' private morning message no longer carries money matters.
    assert "Tekshirilmagan to'lov cheklari" not in await admin_digest.text(db, ten)
