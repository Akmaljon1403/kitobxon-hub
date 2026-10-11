"""Premium paid to the club's card: receipt from the member, confirmation by the super admin."""

from __future__ import annotations

import io
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import EditMessageReplyMarkup, EditMessageText, GetFile, SendPhoto
from aiogram.methods.base import TelegramMethod
from aiogram.types import File
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.models import CardPayment, Notification, PremiumPlan, PremiumSubscription, User
from app.models.enums import CardPaymentStatus, FeatureMode, NotificationType, PremiumSource
from app.services import card_payments, features
from app.services import premium as premium_service
from app.services.settings import update_setting
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role, member_headers


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 1000), (240, 240, 240)).save(buffer, format="JPEG")
    return buffer.getvalue()


async def _open_card_payments(db: AsyncSession, admin: User, *, price: int | None = 25_000) -> PremiumPlan:
    await features.set_mode(db, actor_id=admin.id, code="premium", new_mode=FeatureMode.ALL, announce=False)
    await features.set_mode(db, actor_id=admin.id, code="card_payments", new_mode=FeatureMode.ALL, announce=False)
    await update_setting(db, key="payments.card_number", value="8600 1234 5678 9012", actor_id=admin.id)
    await update_setting(db, key="payments.card_holder", value="A. Bahodirov", actor_id=admin.id)
    plan = await db.scalar(select(PremiumPlan).where(PremiumPlan.code == "month"))
    assert plan is not None
    plan.price_uzs = price
    await db.commit()
    return plan


async def _super_admin(db: AsyncSession, telegram_id: int | None = None) -> User:
    admin = await create_user(db, **({"telegram_id": telegram_id} if telegram_id else {}))
    await db.commit()
    await grant_role(db, admin, "SUPER_ADMIN")
    return admin


async def _submit(client: httpx.AsyncClient, member: User, **form: Any) -> httpx.Response:
    return await client.post(
        "/api/v1/me/premium/card-payments",
        data={key: str(value) for key, value in form.items()},
        files={"file": ("chek.jpg", form.pop("receipt", _jpeg()), "image/jpeg")},
        headers=member_headers(member),
    )


async def test_card_payment_from_the_mini_app(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, first_name="Sevara", last_name="Olimova")
    await db.commit()

    assert (await premium_service.member_status(db, member))["card"] is None
    closed = await _submit(client, member, amount_uzs=5000)
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "CARD_PAYMENTS_OFF"

    plan = await _open_card_payments(db, admin)
    status = (await client.get("/api/v1/me/premium", headers=member_headers(member))).json()
    assert status["card"] == {"number": "8600 1234 5678 9012", "holder": "A. Bahodirov"}
    assert next(p for p in status["plans"] if p["id"] == str(plan.id))["price_uzs"] == 25_000

    sent = await _submit(client, member, plan_id=plan.id)
    assert sent.status_code == 201, sent.text
    assert sent.json()["status"] == "PENDING" and sent.json()["amount_uzs"] == 25_000
    note = await db.scalar(
        select(Notification).where(Notification.user_id == admin.id, Notification.type == NotificationType.PREMIUM)
    )
    assert "Yangi karta to'lovi" in note.text and "Olimova Sevara" in note.text
    callbacks = [b.get("callback") for b in note.payload["buttons"]]
    assert callbacks[0].startswith("cp:view:")

    assert (await _submit(client, member, amount_uzs=500)).status_code == 400  # donation below 1 000
    assert (await _submit(client, member, plan_id=plan.id, amount_uzs=1000)).status_code == 400
    assert (await _submit(client, member, amount_uzs=5000, receipt=b"not a picture")).status_code == 400
    assert (await _submit(client, member, amount_uzs=10_000)).status_code == 201
    assert (await _submit(client, member, amount_uzs=10_000)).status_code == 201
    too_many = await _submit(client, member, amount_uzs=10_000)
    assert too_many.status_code == 409 and too_many.json()["error"]["code"] == "TOO_MANY_PENDING"

    mine = (await client.get("/api/v1/me/premium/card-payments", headers=member_headers(member))).json()
    assert len(mine) == 3 and {item["status"] for item in mine} == {"PENDING"}

    plan.price_uzs = None
    await db.commit()
    not_sold = await _submit(client, member, plan_id=plan.id)
    assert not_sold.status_code in (404, 409)


async def test_super_admin_confirms_or_rejects(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    plain_admin = await create_user(db)
    member = await create_user(db)
    await db.commit()
    await grant_role(db, plain_admin, "ADMIN")
    plan = await _open_card_payments(db, admin)
    first = (await _submit(client, member, plan_id=plan.id)).json()
    second = (await _submit(client, member, amount_uzs=15_000)).json()
    headers = admin_headers(admin)

    assert (
        await client.get("/api/v1/admin/premium/card-payments", headers=admin_headers(plain_admin))
    ).status_code == 403
    pending = (await client.get("/api/v1/admin/premium/card-payments?status=PENDING", headers=headers)).json()
    assert pending["total"] == 2
    receipt = await client.get(f"/api/v1/admin/premium/card-payments/{first['id']}/receipt", headers=headers)
    assert receipt.status_code == 200 and receipt.headers["content-type"] == "image/jpeg"

    approved = await client.post(f"/api/v1/admin/premium/card-payments/{first['id']}/approve", headers=headers)
    assert approved.json() == {"status": "APPROVED"}
    again = await client.post(f"/api/v1/admin/premium/card-payments/{first['id']}/approve", headers=headers)
    assert again.status_code == 409
    subscription = await db.scalar(select(PremiumSubscription).where(PremiumSubscription.user_id == member.id))
    assert subscription.source == PremiumSource.CARD and (subscription.ends_at - subscription.starts_at).days == 30
    assert await premium_service.is_premium(db, member.id)

    rejected = await client.post(
        f"/api/v1/admin/premium/card-payments/{second['id']}/reject",
        json={"reason": "Summa kartaga tushmagan"},
        headers=headers,
    )
    assert rejected.json() == {"status": "REJECTED"}
    texts_for_member = list(
        await db.scalars(
            select(Notification.text).where(
                Notification.user_id == member.id, Notification.type == NotificationType.PREMIUM
            )
        )
    )
    assert any("tasdiqlandi" in text for text in texts_for_member)
    assert any("Summa kartaga tushmagan" in text for text in texts_for_member)

    overview = (await client.get("/api/v1/admin/premium/overview", headers=headers)).json()
    assert overview["uzs_this_month"] == 25_000 and overview["uzs_total"] == 25_000 and overview["card_pending"] == 0
    plans = (await client.get("/api/v1/admin/premium/plans", headers=headers)).json()
    assert next(p for p in plans if p["id"] == str(plan.id))["price_uzs"] == 25_000
    changed = await client.patch(f"/api/v1/admin/premium/plans/{plan.id}", json={"price_uzs": 30_000}, headers=headers)
    assert changed.json()["price_uzs"] == 30_000


class ReceiptTelegram(FakeTelegramSession):
    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, GetFile):
            self.requests.append(method)
            return File(file_id=method.file_id, file_unique_id="r", file_path="photos/chek.jpg")
        return await super().make_request(bot, method, timeout)

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        yield _jpeg()


def _harness(telegram_id: int) -> BotHarness:
    harness = BotHarness(telegram_id)
    harness.session = ReceiptTelegram()
    harness.bot = Bot(token=BOT_TOKEN, session=harness.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return harness


async def test_card_payment_in_the_bot(db: AsyncSession) -> None:
    admin = await _super_admin(db, telegram_id=9301)
    member = await create_user(db, telegram_id=9302, first_name="Bobur")
    stranger = await create_user(db, telegram_id=9303)
    await db.commit()
    plan = await _open_card_payments(db, admin)
    member_id = member.id
    del stranger

    student = _harness(9302)
    await student.send("/premium")
    buttons = [b.callback_data for row in student.session.sent_messages()[-1].reply_markup.inline_keyboard for b in row]
    assert "card:open" in buttons
    await student.press("card:open")
    choose = student.session.sent_messages()[-1]
    assert choose.reply_markup.inline_keyboard[0][0].callback_data == f"card:plan:{plan.id.hex}"
    assert "25 000 so'm" in choose.reply_markup.inline_keyboard[0][0].text

    await student.press(f"card:plan:{plan.id.hex}")
    assert "8600 1234 5678 9012" in student.last_text() and "25 000 so'm" in student.last_text()
    await student.send("to'ladim")
    assert student.last_text() == texts.CARD_RECEIPT_HINT
    await student.send_photo("receipt-file")
    assert student.last_text() == texts.CARD_RECEIPT_OK
    payment = await db.scalar(select(CardPayment).where(CardPayment.user_id == member_id))
    assert payment.status == CardPaymentStatus.PENDING

    # A donation needs no receipt: the card number, then a sincere thank-you.
    await student.press("card:don")
    assert "8600 1234 5678 9012" in student.last_text()
    await student.press("don:done")
    assert student.last_text() == texts.DONATE_THANKS
    await student.press(f"card:plan:{plan.id.hex}")
    await student.send_photo("receipt-2")
    assert student.last_text() == texts.CARD_RECEIPT_OK
    second = await db.scalar(select(CardPayment).where(CardPayment.user_id == member_id, CardPayment.id != payment.id))

    # Only the super admin can decide.
    outsider = _harness(9303)
    await outsider.press(f"cp:ok:{payment.id.hex}")
    assert outsider.session.alerts()[-1] == texts.CARD_ADMIN_ONLY

    boss = _harness(9301)
    await boss.press(f"cp:view:{payment.id.hex}")
    photo = next(r for r in reversed(boss.session.requests) if isinstance(r, SendPhoto))
    assert (
        "Bobur" in photo.caption and photo.reply_markup.inline_keyboard[0][0].callback_data == f"cp:ok:{payment.id.hex}"
    )
    await boss.press(f"cp:ok:{payment.id.hex}")
    edited = next(r for r in reversed(boss.session.requests) if isinstance(r, EditMessageText))
    assert "Tasdiqlandi" in edited.text
    assert edited.reply_markup.inline_keyboard[-1][0].callback_data == f"cp:undo:{payment.id.hex}"
    assert await premium_service.is_premium(db, member_id)

    # A mistake: «↩️ Qaytarish» takes the Premium back and the receipt waits again.
    await boss.press(f"cp:undo:{payment.id.hex}")
    await db.refresh(payment)
    assert payment.status == CardPaymentStatus.PENDING
    assert not await premium_service.is_premium(db, member_id)

    # Rejecting: a ready reason, or one typed in the private chat.
    await boss.press(f"cp:no:{second.id.hex}")
    markup = next(r for r in reversed(boss.session.requests) if isinstance(r, EditMessageReplyMarkup))
    assert markup.reply_markup.inline_keyboard[0][0].callback_data == f"cp:nr:{second.id.hex}:0"
    await boss.press(f"cp:nr:{second.id.hex}:1")
    await db.refresh(second)
    assert second.status == CardPaymentStatus.REJECTED and second.reject_reason == texts.CARD_REJECT_REASONS[1]
    await boss.press(f"cp:undo:{second.id.hex}")
    await boss.press(f"cp:nw:{second.id.hex}")
    assert "rad etish sababini" in boss.last_text()
    await boss.send("Chek boshqa odamniki")
    assert boss.last_text() == texts.CARD_REJECTED
    # The receipt message itself shows the decision, as it does for a ready reason.
    edited = [r for r in boss.session.requests if isinstance(r, EditMessageText)]
    assert edited and "Sabab: Chek boshqa odamniki" in edited[-1].text
    await db.refresh(second)
    assert second.status == CardPaymentStatus.REJECTED and second.reject_reason == "Chek boshqa odamniki"
    assert card_payments.format_uzs(1234567) == "1 234 567 so'm"
