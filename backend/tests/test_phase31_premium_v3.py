"""Premium, round three: lifetime Premium for super admins, the real gold card, premium-only ranking tabs
and certificate PDFs, the free trial, personal discounts, Telegram Stars bought by card, the portfolio."""

from __future__ import annotations

import io
import itertools
from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import AnswerPreCheckoutQuery, CreateInvoiceLink, EditMessageText, GetFile
from aiogram.methods.base import TelegramMethod
from aiogram.types import File, PreCheckoutQuery, SuccessfulPayment, Update
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.models import (
    CardPayment,
    Certificate,
    Notification,
    PremiumDiscount,
    PremiumPlan,
    PremiumSubscription,
    User,
)
from app.models.enums import (
    CardPaymentStatus,
    CertificateKind,
    FeatureMode,
    NotificationType,
    PaymentKind,
    PremiumSource,
    ScoreCategory,
)
from app.services import card_payments, certificates, features
from app.services import passport as passport_service
from app.services import premium as premium_service
from app.services.scoring import award_points
from app.services.settings import update_setting
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role, member_headers

_ids = itertools.count(950_000)
TZ = ZoneInfo(get_settings().timezone)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


class Telegram(FakeTelegramSession):
    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, CreateInvoiceLink):
            self.requests.append(method)
            return "https://t.me/$invoice-test"
        if isinstance(method, GetFile):
            self.requests.append(method)
            return File(file_id=method.file_id, file_unique_id="r", file_path="photos/chek.jpg")
        return await super().make_request(bot, method, timeout)

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        yield _jpeg()


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (500, 800), (240, 240, 240)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _harness(telegram_id: int) -> BotHarness:
    harness = BotHarness(telegram_id)
    harness.session = Telegram()
    harness.bot = Bot(token=BOT_TOKEN, session=harness.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return harness


async def _super_admin(db: AsyncSession, **user: Any) -> User:
    admin = await create_user(db, **user)
    await db.commit()
    await grant_role(db, admin, "SUPER_ADMIN")
    return admin


async def _mode(db: AsyncSession, admin: User, code: str, mode: FeatureMode) -> None:
    await features.set_mode(db, actor_id=admin.id, code=code, new_mode=mode, announce=False)


async def _plan(db: AsyncSession, code: str = "month") -> PremiumPlan:
    plan = await db.scalar(select(PremiumPlan).where(PremiumPlan.code == code))
    assert plan is not None
    return plan


# ---------------------------------------------------------------------------- lifetime Premium, gold card


async def test_super_admins_are_premium_for_life(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db)
    await db.commit()
    admin_id, member_id = admin.id, member.id
    assert await premium_service.is_premium(db, admin_id) and await premium_service.is_lifetime(db, admin_id)
    assert not await premium_service.is_premium(db, member_id)
    assert await premium_service.premium_among(db, [admin_id, member_id]) == {admin_id}

    me = (await client.get("/api/v1/me", headers=member_headers(admin))).json()
    assert me["is_premium"] and me["premium_lifetime"] and me["premium_until"] is None
    status = (await client.get("/api/v1/me/premium", headers=member_headers(admin))).json()
    assert status["lifetime"] is True and status["trial_days"] == 0

    # The gold design is open to the super admin without buying anything.
    chosen = await client.put("/api/v1/me/passport/theme", json={"theme": "gold"}, headers=member_headers(admin))
    assert chosen.status_code == 204
    assert (await passport_service.collect(db, await db.get(User, admin_id))).theme == "gold"

    # A gift «for life» from the Admin Panel.
    given = await client.post(
        "/api/v1/admin/premium/grant",
        json={"user_id": str(member_id), "lifetime": True, "note": "Klub asoschisi"},
        headers=admin_headers(admin),
    )
    assert given.status_code == 201, given.text
    assert given.json()["ends_at"].startswith("2099")
    assert await premium_service.is_lifetime(db, member_id)
    missing = await client.post(
        "/api/v1/admin/premium/grant", json={"user_id": str(member_id)}, headers=admin_headers(admin)
    )
    assert missing.status_code == 400


def test_the_gold_card_is_gold() -> None:
    data = passport_service.PassportData(
        number="KH-000001",
        first_name="Ali",
        last_name="Valiyev",
        faculty=None,
        course=1,
        group_name="101",
        member_since="01.10.2026",
        verify_url="https://kitobxon.example.org/v/ABC",
        active=True,
        premium=True,
        theme="gold",
        organization="Klub",
    )
    image = Image.open(io.BytesIO(passport_service.draw_passport(data))).convert("RGB")
    r, g, b = image.getpixel((1100, 736))  # the bottom-right corner of the gradient, under the QR code
    assert r > 200 and g > 160 and r - b > 60  # bright metal, not dark green
    assert set(passport_service.THEMES) >= {"gold", "silver", "ocean", "lavender"}


# ---------------------------------------------------------------------------- what Premium unlocks


async def test_ranking_week_is_free_the_rest_premium(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, telegram_id=9601)
    await award_points(db, user_id=member.id, amount=20, category=ScoreCategory.ATTENDANCE, idempotency_key="r1")
    await db.commit()
    headers = member_headers(member)

    week = await client.get("/api/v1/rankings?period=week&scope=all", headers=headers)
    assert week.status_code == 200 and week.json()["me"]["total"] == 20
    for query in ("period=month&scope=all", "period=all&scope=all", "period=week&scope=faculty"):
        locked = await client.get(f"/api/v1/rankings?{query}", headers=headers)
        assert locked.status_code == 403 and locked.json()["error"]["code"] == "PREMIUM_REQUIRED", query
    assert (await client.get("/api/v1/rankings/faculties", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/me/ranking", headers=headers)).status_code == 200  # own places stay free

    harness = _harness(9601)
    await harness.send(texts.BTN_RANKING)
    assert "Shu hafta yetakchilari" in harness.last_text() and "Premium" in harness.last_text()

    await premium_service.grant(db, actor_id=admin.id, user_id=member.id, days=30, note=None)
    assert (await client.get("/api/v1/rankings?period=month&scope=all", headers=headers)).status_code == 200
    await harness.send(texts.BTN_RANKING)
    assert "Shu oy yetakchilari" in harness.last_text()

    await _mode(db, admin, "ranking_full", FeatureMode.ALL)  # the owner can open it for everyone
    other = await create_user(db)
    await db.commit()
    assert (await client.get("/api/v1/rankings?period=all", headers=member_headers(other))).status_code == 200


async def test_certificate_pdf_is_premium_or_limited(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, telegram_id=9602)
    await db.commit()
    member_id = member.id
    certificate = await certificates.issue(
        db,
        user_id=member_id,
        kind=CertificateKind.MANUAL,
        title="Faol kitobxon",
        description="Faol ishtiroki uchun taqdim etiladi.",
        dedup_key="pdf-test",
    )
    await db.commit()
    note = await db.scalar(select(Notification).where(Notification.dedup_key == f"certificate:{certificate.id}"))
    assert "certificate_id" not in note.payload  # the bot never attaches it: the app shows it
    assert "https://kitobxon.example.org/v/" in note.text

    headers = member_headers(member)
    listed = (await client.get("/api/v1/me/certificates", headers=headers)).json()
    assert listed[0]["verify_url"].startswith("https://kitobxon.example.org/v/")  # sharing the check link is free
    assert listed[0]["rights"]["downloads_left"] == 1 and listed[0]["rights"]["can_change_design"] is False
    pdf = await client.get(f"/api/v1/me/certificates/{certificate.id}/pdf", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")  # one free download
    pdf = await client.get(f"/api/v1/me/certificates/{certificate.id}/pdf", headers=headers)
    assert pdf.status_code == 403 and pdf.json()["error"]["code"] == "PREMIUM_REQUIRED"
    link = await client.post(
        "/api/v1/me/downloads", json={"kind": "certificate", "id": str(certificate.id)}, headers=headers
    )
    assert link.status_code == 403
    design = await client.put(
        f"/api/v1/me/certificates/{certificate.id}/design", json={"design": "ocean"}, headers=headers
    )
    assert design.status_code == 403  # changing the design is Premium

    await premium_service.grant(db, actor_id=admin.id, user_id=member_id, days=7, note=None)
    for _ in range(2):
        pdf = await client.get(f"/api/v1/me/certificates/{certificate.id}/pdf", headers=headers)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")  # Premium: unlimited
    detail = (await client.get(f"/api/v1/me/certificates/{certificate.id}", headers=headers)).json()
    assert detail["rights"]["downloads_left"] is None and detail["rights"]["design_changes_left"] == 3
    assert await db.scalar(select(Certificate.id).where(Certificate.id == certificate.id))


async def test_portfolio_pdf(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, first_name="Malika", last_name="Yusupova")
    await db.commit()
    headers = member_headers(member)
    assert (await client.get("/api/v1/me/portfolio", headers=headers)).status_code == 403
    await premium_service.grant(db, actor_id=admin.id, user_id=member.id, days=7, note=None)
    pdf = await client.get("/api/v1/me/portfolio", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "Kitobxonlik-portfoliosi-KH-" in pdf.headers["content-disposition"]
    link = (await client.post("/api/v1/me/downloads", json={"kind": "portfolio"}, headers=headers)).json()
    file = await client.get(link["url"].removeprefix("https://kitobxon.example.org"))
    assert file.status_code == 200 and file.content.startswith(b"%PDF")


# ---------------------------------------------------------------------------- trial, discounts


async def test_free_trial_once_and_a_reminder_before_the_end(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, telegram_id=9603)
    await db.commit()
    member_id = member.id
    headers = member_headers(member)
    assert (await client.get("/api/v1/me/premium", headers=headers)).json()["trial_days"] == 0  # store closed
    await _mode(db, admin, "premium", FeatureMode.ALL)
    assert (await client.get("/api/v1/me/premium", headers=headers)).json()["trial_days"] == 7

    harness = _harness(9603)
    await harness.send("/premium")
    buttons = [b.callback_data for row in harness.session.sent_messages()[-1].reply_markup.inline_keyboard for b in row]
    assert "prem:trial" not in buttons  # the trial starts by itself at registration now
    await harness.press("prem:trial")  # a button of an older message still works once
    assert "Bepul Premium boshlandi" in harness.last_text()
    assert await premium_service.is_premium(db, member_id)
    again = await client.post("/api/v1/me/premium/trial", headers=headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "TRIAL_UNAVAILABLE"
    subscription = await db.scalar(select(PremiumSubscription).where(PremiumSubscription.user_id == member_id))
    assert subscription.source == PremiumSource.TRIAL and (subscription.ends_at - subscription.starts_at).days == 7

    # One message the day before the end, in the daytime, and only once.
    # A moment less than a day before the end, in the club's daytime (10:00–20:00).
    day_before = next(
        moment
        for hours in range(2, 26)
        if 10 <= (moment := subscription.ends_at - timedelta(hours=hours)).astimezone(TZ).hour < 20
    )
    assert await premium_service.remind_expiring(db, now=day_before) == 1
    await db.commit()
    await premium_service.remind_expiring(db, now=day_before + timedelta(minutes=5))
    await db.commit()
    reminders = list(
        await db.scalars(select(Notification).where(Notification.dedup_key == f"premium:ending:{subscription.id}"))
    )
    assert len(reminders) == 1 and "sinovingiz ertaga tugaydi" in reminders[0].text
    await update_setting(db, key="premium.trial_days", value=0, actor_id=admin.id)
    other = await create_user(db)
    await db.commit()
    assert (await client.get("/api/v1/me/premium", headers=member_headers(other))).json()["trial_days"] == 0


async def test_personal_discount_lowers_stars_and_card_prices(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, telegram_id=9604)
    await db.commit()
    member_id = member.id
    await _mode(db, admin, "premium", FeatureMode.ALL)
    await _mode(db, admin, "card_payments", FeatureMode.ALL)
    await update_setting(db, key="payments.card_number", value="8600 0000 0000 0001", actor_id=admin.id)
    plan = await _plan(db)
    stars, uzs = plan.stars, plan.price_uzs
    discount = await premium_service.give_discount(db, user_id=member_id, percent=50, days=10, note="Yangi a'zo")
    await db.commit()
    discount_id = discount.id
    with pytest.raises(Exception, match="90%"):
        await premium_service.give_discount(db, user_id=member_id, percent=95, days=1, note="x")
    await db.rollback()

    headers = member_headers(member)
    status = (await client.get("/api/v1/me/premium", headers=headers)).json()
    month = next(p for p in status["plans"] if p["id"] == str(plan.id))
    assert status["discount"]["percent"] == 50
    assert month["stars_now"] == round(stars / 2) and month["price_uzs_now"] == round(uzs / 2 / 100) * 100

    # Stars: the invoice carries the discount; Telegram's pre-checkout is checked against it.
    harness = _harness(9604)
    await harness.press(f"prem:buy:{plan.id.hex}")
    invoice = next(r for r in harness.session.requests if r.__class__.__name__ == "SendInvoice")
    assert invoice.prices[0].amount == round(stars / 2) and invoice.payload.endswith(discount_id.hex)
    query = PreCheckoutQuery(
        id=str(next(_ids)), from_user=harness.user, currency="XTR", total_amount=stars, invoice_payload=invoice.payload
    )
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), pre_checkout_query=query))
    answer = [r for r in harness.session.requests if isinstance(r, AnswerPreCheckoutQuery)][-1]
    assert answer.ok is False  # the full price with a discount payload is refused
    query = query.model_copy(update={"id": str(next(_ids)), "total_amount": round(stars / 2)})
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), pre_checkout_query=query))
    assert [r for r in harness.session.requests if isinstance(r, AnswerPreCheckoutQuery)][-1].ok is True
    paid = SuccessfulPayment(
        currency="XTR",
        total_amount=round(stars / 2),
        invoice_payload=invoice.payload,
        telegram_payment_charge_id="disc-1",
        provider_payment_charge_id="",
    )
    await harness.dispatcher.feed_update(
        harness.bot, Update(update_id=next(_ids), message=harness._message(successful_payment=paid))
    )
    used = await db.get(PremiumDiscount, discount_id)
    await db.refresh(used)
    assert used.used_at is not None and used.used_for.startswith("payment:")
    assert (await client.get("/api/v1/me/premium", headers=headers)).json()["discount"] is None

    # Card: a new discount lowers the so'm price and is used when the receipt is confirmed.
    second = await premium_service.give_discount(db, user_id=member_id, percent=20, days=3, note="Aksiya")
    await db.commit()
    second_id = second.id
    sent = await client.post(
        "/api/v1/me/premium/card-payments",
        data={"plan_id": str(plan.id)},
        files={"file": ("chek.jpg", _jpeg(), "image/jpeg")},
        headers=headers,
    )
    assert sent.status_code == 201 and sent.json()["amount_uzs"] == round(uzs * 0.8 / 100) * 100
    await card_payments.approve(db, actor_id=admin.id, payment_id=__import__("uuid").UUID(sent.json()["id"]))
    second = await db.get(PremiumDiscount, second_id)
    await db.refresh(second)
    assert second.used_for.startswith("card:")


# ---------------------------------------------------------------------------- Stars bought with a card


async def test_stars_bought_by_card_are_gifted_by_the_admin(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db, telegram_id=9610)
    member = await create_user(db, telegram_id=9611, first_name="Nodir", telegram_username="nodir_reads")
    await db.commit()
    member_id = member.id
    await _mode(db, admin, "card_payments", FeatureMode.ALL)
    await update_setting(db, key="payments.card_number", value="8600 0000 0000 0002", actor_id=admin.id)
    await update_setting(db, key="payments.star_price_uzs", value=230, actor_id=admin.id)
    offer = await card_payments.stars_offer(db)
    assert offer[1] == {"stars": 100, "price_uzs": 23000} and offer[0] == {"stars": 50, "price_uzs": 11500}

    status = (await client.get("/api/v1/me/premium", headers=member_headers(member))).json()
    assert status["stars_packages"][1]["stars"] == 100
    wrong = await client.post(
        "/api/v1/me/premium/card-payments",
        data={"stars": "77"},
        files={"file": ("chek.jpg", _jpeg(), "image/jpeg")},
        headers=member_headers(member),
    )
    assert wrong.status_code == 404

    student = _harness(9611)
    await student.press("card:open")
    keyboard = student.session.sent_messages()[-1].reply_markup.inline_keyboard
    assert any(b.callback_data == "card:stars:100" for row in keyboard for b in row)
    await student.press("card:stars:100")
    assert "100 Telegram Stars" in student.last_text() and "23 000 so'm" in student.last_text()
    await student.send_photo("receipt")
    assert student.last_text() == texts.CARD_RECEIPT_OK
    payment = await db.scalar(select(CardPayment).where(CardPayment.user_id == member_id))
    assert payment.kind == PaymentKind.STARS and payment.stars == 100 and payment.amount_uzs == 23000
    payment_id = payment.id

    boss = _harness(9610)
    await boss.press(f"cp:ok:{payment_id.hex}")
    # Nobody has «⭐ Stars yuborish»: the order comes to the super admin's private chat, with the steps.
    order = await db.scalar(
        select(Notification).where(
            Notification.user_id == admin.id, Notification.dedup_key.like(f"stars-order:{payment_id}:%")
        )
    )
    # The Stars are bought on Fragment for the member's current Telegram username.
    assert "100 Stars'ni yuboring" in order.text and "fragment.com" in order.text and "@akmal_reader" in order.text
    assert "tg://user?id=9611" in order.text and "Bosh admin tomonidan tasdiqlandi" in order.text
    assert order.payload["buttons"][0]["callback"] == f"cp:sent:{payment_id.hex}"

    waiting = (
        await client.get("/api/v1/admin/premium/card-payments?status=PENDING", headers=admin_headers(admin))
    ).json()
    assert waiting["total"] == 1 and waiting["items"][0]["kind"] == "STARS"  # confirmed, not yet gifted
    await boss.press(f"cp:sent:{payment_id.hex}")
    sent = next(r for r in reversed(boss.session.requests) if isinstance(r, EditMessageText))
    assert "Stars yuborildi" in sent.text
    await boss.press(f"cp:sent:{payment_id.hex}")
    assert "allaqachon" in boss.session.alerts()[-1]
    messages = list(
        await db.scalars(
            select(Notification.text).where(
                Notification.user_id == member_id, Notification.type == NotificationType.PREMIUM
            )
        )
    )
    assert any("tez orada Telegram'da" in text for text in messages)
    assert any("100 Stars sizga sovg'a qilindi" in text for text in messages)
    mine = (await client.get("/api/v1/me/premium/card-payments", headers=member_headers(member))).json()
    assert mine[0]["stars"] == 100 and mine[0]["delivered_at"] is not None
    done = (await client.get("/api/v1/admin/premium/card-payments?status=PENDING", headers=admin_headers(admin))).json()
    assert done["total"] == 0
    stored = await db.get(CardPayment, payment_id)
    await db.refresh(stored)
    assert stored.status == CardPaymentStatus.APPROVED and stored.delivered_at is not None
