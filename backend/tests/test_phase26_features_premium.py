"""Feature switches with announcements, Premium with Telegram Stars, donations, event feedback,
the weekly digest, and general / period reports."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import (
    AnswerPreCheckoutQuery,
    CreateInvoiceLink,
    EditMessageText,
    RefundStarPayment,
    SendInvoice,
)
from aiogram.methods.base import TelegramMethod
from aiogram.types import PreCheckoutQuery, ReplyKeyboardMarkup, SuccessfulPayment, Update
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.models import (
    AttendanceRecord,
    BookQuote,
    EventFeedback,
    Notification,
    Payment,
    PremiumPlan,
    PremiumSubscription,
    User,
)
from app.models.enums import (
    AttendanceMethod,
    FeatureMode,
    NotificationType,
    PaymentKind,
    PaymentStatus,
    QuoteStatus,
    ScoreCategory,
)
from app.services import announcements, features
from app.services import feedback as feedback_service
from app.services import passport as passport_service
from app.services import premium as premium_service
from app.services.scoring import award_points
from app.workers.sender import _markup
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_event, create_user
from tests.helpers import admin_headers, grant_role, member_headers

_ids = itertools.count(900_000)
TZ = ZoneInfo(get_settings().timezone)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


class StarsTelegram(FakeTelegramSession):
    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, CreateInvoiceLink):
            self.requests.append(method)
            return "https://t.me/$invoice-test"
        return await super().make_request(bot, method, timeout)


def _install_bot(monkeypatch: pytest.MonkeyPatch) -> StarsTelegram:
    telegram = StarsTelegram()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: SimpleNamespace(bot=bot))
    return telegram


async def _super_admin(db: AsyncSession) -> User:
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "SUPER_ADMIN")
    return admin


async def _set(db: AsyncSession, admin: User, code: str, mode: FeatureMode, announce: bool = False) -> int:
    return await features.set_mode(db, actor_id=admin.id, code=code, new_mode=mode, announce=announce)


async def _plan(db: AsyncSession, code: str = "month") -> PremiumPlan:
    plan = await db.scalar(select(PremiumPlan).where(PremiumPlan.code == code))
    assert plan is not None
    return plan


async def _pay(harness: BotHarness, payload: str, amount: int, charge: str) -> None:
    """What Telegram sends: the pre-checkout question, then the successful payment message."""
    query = PreCheckoutQuery(
        id=str(next(_ids)), from_user=harness.user, currency="XTR", total_amount=amount, invoice_payload=payload
    )
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), pre_checkout_query=query))
    paid = SuccessfulPayment(
        currency="XTR",
        total_amount=amount,
        invoice_payload=payload,
        telegram_payment_charge_id=charge,
        provider_payment_charge_id="",
    )
    await harness.dispatcher.feed_update(
        harness.bot, Update(update_id=next(_ids), message=harness._message(successful_payment=paid))
    )


def _precheckout_answers(harness: BotHarness) -> list[AnswerPreCheckoutQuery]:
    return [r for r in harness.session.requests if isinstance(r, AnswerPreCheckoutQuery)]


# ---------------------------------------------------------------------------- feature switches


async def test_switching_features_off_and_to_premium(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db)
    await db.commit()

    me = (await client.get("/api/v1/me", headers=member_headers(member))).json()
    assert me["features"]["achievements"] == "on" and me["features"]["weekly_digest"] == "premium"
    assert me["features"]["premium"] == "off" and me["is_premium"] is False

    await _set(db, admin, "achievements", FeatureMode.OFF)
    off = await client.get("/api/v1/me/achievements", headers=member_headers(member))
    assert off.status_code == 403 and off.json()["error"]["code"] == "FEATURE_OFF"

    await _set(db, admin, "ranking", FeatureMode.PREMIUM)
    locked = await client.get("/api/v1/rankings?period=month&scope=all", headers=member_headers(member))
    assert locked.status_code == 403 and locked.json()["error"]["code"] == "PREMIUM_REQUIRED"
    assert (await client.get("/api/v1/me/scores", headers=member_headers(member))).status_code == 200  # core stays

    await premium_service.grant(db, actor_id=admin.id, user_id=member.id, days=30, note="Test")
    assert (
        await client.get("/api/v1/rankings?period=month&scope=all", headers=member_headers(member))
    ).status_code == 200
    me = (await client.get("/api/v1/me", headers=member_headers(member))).json()
    assert me["is_premium"] is True and me["premium_until"] and me["features"]["ranking"] == "on"

    with pytest.raises(Exception, match="faqat yoqish"):
        await _set(db, admin, "premium", FeatureMode.PREMIUM)


async def test_switching_on_announces_the_feature(db: AsyncSession) -> None:
    admin = await _super_admin(db)
    members = [await create_user(db) for _ in range(3)]
    await db.commit()
    await _set(db, admin, "passport", FeatureMode.OFF)
    assert await _set(db, admin, "passport", FeatureMode.ALL, announce=True) == 4  # three members + the admin
    text = await db.scalar(
        select(Notification.text).where(
            Notification.type == NotificationType.ANNOUNCEMENT, Notification.user_id == members[0].id
        )
    )
    assert "Tabriklaymiz, bot yangilandi" in text and "Kitobxon pasporti" in text

    # Premium only: premium members get the news; the others get a teaser only while the store is open.
    await premium_service.grant(db, actor_id=admin.id, user_id=members[1].id, days=10, note=None)
    await _set(db, admin, "certificates", FeatureMode.OFF)
    # The member with Premium and the super admin (Premium for life).
    assert await _set(db, admin, "certificates", FeatureMode.PREMIUM, announce=True) == 2
    await _set(db, admin, "premium", FeatureMode.ALL)
    await _set(db, admin, "achievements", FeatureMode.OFF)
    assert await _set(db, admin, "achievements", FeatureMode.PREMIUM, announce=True) == 4
    teaser = await db.scalar(
        select(Notification.text)
        .where(Notification.user_id == members[0].id, Notification.text.like("%Premium a'zolar uchun%"))
        .limit(1)
    )
    assert teaser is not None
    # Same mode again or switching off: nobody is told.
    assert await _set(db, admin, "achievements", FeatureMode.PREMIUM, announce=True) == 0
    assert await _set(db, admin, "achievements", FeatureMode.OFF, announce=True) == 0


async def test_feature_admin_api_is_for_the_super_admin(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    plain = await create_user(db)
    await db.commit()
    await grant_role(db, plain, "ADMIN")

    assert (await client.get("/api/v1/admin/features", headers=admin_headers(plain))).status_code == 403
    listed = (await client.get("/api/v1/admin/features", headers=admin_headers(admin))).json()
    assert {row["code"] for row in listed} >= {"passport", "premium", "weekly_digest", "event_feedback"}
    changed = await client.put(
        "/api/v1/admin/features/support", json={"mode": "OFF", "announce": False}, headers=admin_headers(admin)
    )
    assert changed.json() == {"code": "support", "mode": "OFF", "announced_to": 0}
    missing = await client.put("/api/v1/admin/features/nope", json={"mode": "OFF"}, headers=admin_headers(admin))
    assert missing.status_code == 404


async def test_bot_menu_hides_switched_off_sections(db: AsyncSession) -> None:
    admin = await _super_admin(db)
    await create_user(db, telegram_id=8101)
    await db.commit()
    await _set(db, admin, "ranking", FeatureMode.OFF)
    await _set(db, admin, "achievements", FeatureMode.PREMIUM)
    harness = BotHarness(8101)

    await harness.send("/menu")
    keyboard = harness.session.sent_messages()[-1].reply_markup
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    labels = [button.text for row in keyboard.keyboard for button in row]
    assert texts.BTN_RANKING not in labels and texts.BTN_ACHIEVEMENTS in labels
    assert all(len(row) <= 2 for row in keyboard.keyboard)

    await harness.send(texts.BTN_RANKING)  # an old keyboard may still show it
    assert "o'chirilgan" in harness.last_text()
    await harness.send(texts.BTN_ACHIEVEMENTS)
    assert "Premium" in harness.last_text()
    markup = harness.session.sent_messages()[-1].reply_markup
    assert markup.inline_keyboard[0][0].callback_data == "prem:open"

    await _set(db, admin, "support", FeatureMode.OFF)
    await harness.send(texts.BTN_HELP)
    buttons = [b.callback_data for row in harness.session.sent_messages()[-1].reply_markup.inline_keyboard for b in row]
    assert "sup:new" not in buttons and "prem:open" not in buttons
    await harness.press("sup:new")
    assert "o'chirilgan" in harness.last_text()


# ---------------------------------------------------------------------------- premium and payments


async def test_premium_purchase_in_the_bot(db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, telegram_id=8201)
    await db.commit()
    harness = BotHarness(8201)

    await harness.send("/premium")
    assert harness.last_text() == texts.PREMIUM_CLOSED

    await _set(db, admin, "premium", FeatureMode.ALL)
    await _set(db, admin, "donations", FeatureMode.ALL)
    await harness.send("/premium")
    message = harness.session.sent_messages()[-1]
    assert "Kitobxon Premium" in message.text and "Haftalik xulosa" in message.text
    plan = await _plan(db)
    callbacks = [b.callback_data for row in message.reply_markup.inline_keyboard for b in row]
    assert f"prem:buy:{plan.id.hex}" in callbacks and "don:open" in callbacks

    await harness.press(f"prem:buy:{plan.id.hex}")
    invoice = next(r for r in reversed(harness.session.requests) if isinstance(r, SendInvoice))
    assert invoice.currency == "XTR" and invoice.prices[0].amount == plan.stars
    assert premium_service.parse_payload(invoice.payload).plan_id == plan.id

    await _pay(harness, invoice.payload, plan.stars, "charge-1")
    assert _precheckout_answers(harness)[-1].ok is True
    assert "Premium faollashtirildi" in harness.last_text()
    assert await premium_service.is_premium(db, member.id)

    # The same update again changes nothing; a second purchase is added after the first period.
    await _pay(harness, invoice.payload, plan.stars, "charge-1")
    assert await db.scalar(select(func.count()).select_from(Payment)) == 1
    await _pay(harness, premium_service.premium_payload(plan, member), plan.stars, "charge-2")
    periods = list(await db.scalars(select(PremiumSubscription).order_by(PremiumSubscription.starts_at)))
    assert len(periods) == 2 and periods[1].starts_at == periods[0].ends_at
    until = await premium_service.premium_until(db, member.id)
    assert until is not None and until - datetime.now(UTC) > timedelta(days=59)

    # Donations.
    await harness.press("don:open")
    assert "qo'llab-quvvatlash" in harness.last_text()
    await harness.press("don:100")
    donation = next(r for r in reversed(harness.session.requests) if isinstance(r, SendInvoice))
    await _pay(harness, donation.payload, 100, "charge-3")
    assert "100 ⭐" in harness.last_text()
    kinds = sorted(str(k) for k in await db.scalars(select(Payment.kind)))
    assert kinds == ["DONATION", "PREMIUM", "PREMIUM"]


async def test_pre_checkout_refuses_wrong_payments(db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, telegram_id=8301)
    other = await create_user(db, telegram_id=8302)
    await db.commit()
    plan = await _plan(db)
    payload = premium_service.premium_payload(plan, member)

    async def check(**overrides: Any) -> str | None:
        values = {"telegram_user_id": 8301, "payload": payload, "currency": "XTR", "total_amount": plan.stars}
        values.update(overrides)
        return await premium_service.check_pre_checkout(db, **values)

    assert "yopiq" in (await check()) or "o'chirilgan" in (await check())  # store still closed
    await _set(db, admin, "premium", FeatureMode.ALL)
    assert await check() is None
    assert await check(telegram_user_id=8302) == "Bu to'lov boshqa a'zo uchun tayyorlangan."
    assert "narxi" in await check(total_amount=plan.stars - 1)
    assert await check(currency="USD") is not None
    assert await check(payload="premium:bad") is not None
    plan.is_active = False
    await db.commit()
    assert "sotuvda" in await check()
    assert (
        await check(payload=premium_service.donation_payload(50, member), total_amount=50) is not None
    )  # donations off
    del other


async def test_mini_app_invoice_link(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await _super_admin(db)
    member = await create_user(db)
    await db.commit()
    plan = await _plan(db, "year")

    status = (await client.get("/api/v1/me/premium", headers=member_headers(member))).json()
    assert status["store_open"] is False and [p["days"] for p in status["plans"]] == [30, 90, 365]

    closed = await client.post(
        "/api/v1/me/premium/invoice", json={"plan_id": str(plan.id)}, headers=member_headers(member)
    )
    assert closed.status_code == 503  # no bot in this test yet
    telegram = _install_bot(monkeypatch)
    closed = await client.post(
        "/api/v1/me/premium/invoice", json={"plan_id": str(plan.id)}, headers=member_headers(member)
    )
    assert closed.status_code == 403 and closed.json()["error"]["code"] == "FEATURE_OFF"

    await _set(db, admin, "premium", FeatureMode.ALL)
    link = await client.post(
        "/api/v1/me/premium/invoice", json={"plan_id": str(plan.id)}, headers=member_headers(member)
    )
    assert link.json() == {"url": "https://t.me/$invoice-test"}
    request = next(r for r in telegram.requests if isinstance(r, CreateInvoiceLink))
    assert request.currency == "XTR" and request.prices[0].amount == plan.stars
    both = await client.post(
        "/api/v1/me/premium/invoice", json={"plan_id": str(plan.id), "amount": 5}, headers=member_headers(member)
    )
    assert both.status_code == 422


async def test_admin_premium_tools(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, telegram_id=8401)
    await db.commit()
    await _set(db, admin, "premium", FeatureMode.ALL)
    plan = await _plan(db)
    await premium_service.record_payment(
        db,
        telegram_user_id=8401,
        payload=premium_service.premium_payload(plan, member),
        currency="XTR",
        total_amount=plan.stars,
        charge_id="charge-admin",
    )
    headers = admin_headers(admin)

    overview = (await client.get("/api/v1/admin/premium/overview", headers=headers)).json()
    # The buyer and the super admin (Premium for life).
    assert overview["premium_members"] == 2 and overview["stars_total"] == plan.stars
    payments = (await client.get("/api/v1/admin/premium/payments", headers=headers)).json()
    assert payments["items"][0]["plan_title"] == "1 oy" and payments["items"][0]["member"]["member_number"].startswith(
        "KH-"
    )

    changed = await client.patch(
        f"/api/v1/admin/premium/plans/{plan.id}", json={"stars": 150, "is_active": False}, headers=headers
    )
    assert changed.json()["stars"] == 150 and changed.json()["is_active"] is False
    status = (await client.get("/api/v1/me/premium", headers=member_headers(member))).json()
    assert [p["days"] for p in status["plans"]] == [90, 365]

    granted = await client.post(
        "/api/v1/admin/premium/grant", json={"user_id": str(member.id), "days": 7, "note": "G'olib"}, headers=headers
    )
    assert granted.status_code == 201 and granted.json()["source"] == "MANUAL"
    subscriptions = (await client.get("/api/v1/admin/premium/subscriptions", headers=headers)).json()
    assert subscriptions["total"] == 2

    telegram = _install_bot(monkeypatch)
    payment_id = payments["items"][0]["id"]
    refunded = await client.post(f"/api/v1/admin/premium/payments/{payment_id}/refund", headers=headers)
    assert refunded.json() == {"status": "REFUNDED"}
    refund_call = next(r for r in telegram.requests if isinstance(r, RefundStarPayment))
    assert refund_call.user_id == 8401 and refund_call.telegram_payment_charge_id == "charge-admin"
    again = await client.post(f"/api/v1/admin/premium/payments/{payment_id}/refund", headers=headers)
    assert again.status_code == 409
    assert (await db.scalar(select(Payment.status))) == PaymentStatus.REFUNDED

    revoked = await client.post(
        f"/api/v1/admin/premium/subscriptions/{granted.json()['id']}/revoke",
        json={"reason": "Xato bilan berilgan"},
        headers=headers,
    )
    assert revoked.json() == {"status": "REVOKED"}
    assert not await premium_service.is_premium(db, member.id)
    notes = list(await db.scalars(select(Notification.text).where(Notification.type == NotificationType.PREMIUM)))
    assert any("sovg'a qilindi" in text for text in notes) and any("qaytarildi" in text for text in notes)


async def test_premium_members_get_the_gold_passport(db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db)
    await db.commit()
    assert (await passport_service.collect(db, member)).premium is False
    await premium_service.grant(db, actor_id=admin.id, user_id=member.id, days=1, note=None)
    data = await passport_service.collect(db, member)
    assert data.premium is True and data.organization.startswith("Farg'ona")
    assert passport_service.draw_passport(data).startswith(b"\x89PNG")


async def test_terms_and_paysupport(db: AsyncSession) -> None:
    await create_user(db, telegram_id=8501)
    await db.commit()
    harness = BotHarness(8501)
    await harness.send("/terms")
    assert "Foydalanish shartlari" in harness.last_text()
    await harness.send("/paysupport")
    assert "To'lov bo'yicha yordam" in harness.last_text()


# ---------------------------------------------------------------------------- feedback and digest


async def test_feedback_is_asked_after_the_event_and_saved(client: httpx.AsyncClient, db: AsyncSession) -> None:
    present = await create_user(db, telegram_id=8601)
    absent = await create_user(db, telegram_id=8602)
    viewer = await create_user(db)
    start = datetime.now(UTC) - timedelta(hours=3)
    event = await create_event(db, title="Kitob kechasi", starts_at=start, ends_at=start + timedelta(hours=2))
    event_id = event.id
    db.add(AttendanceRecord(event_id=event_id, user_id=present.id, method=AttendanceMethod.CODE))
    await db.commit()
    await grant_role(db, viewer, "SUPER_ADMIN")

    assert await feedback_service.request_feedback(db) == 1
    assert await feedback_service.request_feedback(db) == 0  # once
    notification = await db.scalar(select(Notification).where(Notification.type == NotificationType.FEEDBACK_REQUEST))
    assert notification.user_id == present.id and "«Kitob kechasi»" in notification.text
    stars = _markup(notification.payload).inline_keyboard
    assert len(stars) == 1 and [b.callback_data for b in stars[0]][-1] == f"fb:{event_id.hex}:5"

    harness = BotHarness(8601)
    await harness.press(f"fb:{event_id.hex}:4")
    edited = next(r for r in reversed(harness.session.requests) if isinstance(r, EditMessageText))
    assert "4/5" in edited.text and edited.reply_markup.inline_keyboard[0][0].callback_data == f"fbc:{event_id.hex}"
    await harness.press(f"fbc:{event_id.hex}")
    await harness.send("Juda yoqdi, keyingi safar ko'proq vaqt bo'lsa")
    assert harness.last_text() == texts.FEEDBACK_COMMENT_SAVED

    stranger = BotHarness(8602)
    await stranger.press(f"fb:{event_id.hex}:1")
    assert "qatnashganlar uchun" in stranger.session.alerts()[-1]

    mine = await client.get(f"/api/v1/events/{event_id}/feedback", headers=member_headers(present))
    assert mine.json()["rating"] == 4 and "Juda yoqdi" in mine.json()["comment"]
    changed = await client.put(
        f"/api/v1/events/{event_id}/feedback", json={"rating": 5, "comment": "Zo'r"}, headers=member_headers(present)
    )
    assert changed.json()["rating"] == 5
    refused = await client.put(
        f"/api/v1/events/{event_id}/feedback", json={"rating": 3}, headers=member_headers(absent)
    )
    assert refused.status_code == 409
    assert (await client.get(f"/api/v1/events/{event_id}/feedback", headers=member_headers(absent))).json() is None

    summary = (await client.get(f"/api/v1/admin/events/{event_id}/feedback", headers=admin_headers(viewer))).json()
    assert summary["count"] == 1 and summary["average"] == 5.0 and summary["distribution"]["5"] == 1
    assert summary["comments"][0]["comment"] == "Zo'r"


async def test_feedback_and_quotes_follow_their_switches(db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db)
    start = datetime.now(UTC) - timedelta(hours=3)
    event = await create_event(db, starts_at=start, ends_at=start + timedelta(hours=2))
    db.add(AttendanceRecord(event_id=event.id, user_id=member.id, method=AttendanceMethod.QR))
    today = datetime.now(TZ).date()
    quote = BookQuote(text="Kitob — eng yaxshi do'st", status=QuoteStatus.SCHEDULED, scheduled_date=today)
    db.add(quote)
    await db.commit()
    await _set(db, admin, "event_feedback", FeatureMode.OFF)
    await _set(db, admin, "quote_of_day", FeatureMode.OFF)
    assert await feedback_service.request_feedback(db) == 0
    noon = datetime.now(TZ).replace(hour=12, minute=0)
    assert await announcements.quote_of_day(db, now=noon) == 0
    await db.refresh(quote)
    assert quote.status == QuoteStatus.SCHEDULED  # sent later if switched back on today
    await _set(db, admin, "quote_of_day", FeatureMode.PREMIUM)
    await premium_service.grant(db, actor_id=admin.id, user_id=member.id, days=3, note=None)
    assert await announcements.quote_of_day(db, now=noon) == 2  # the member and the super admin
    assert await db.scalar(select(func.count()).select_from(EventFeedback)) == 0


async def test_weekly_digest_for_premium_members(db: AsyncSession) -> None:
    admin = await _super_admin(db)
    reader = await create_user(db, first_name="Diyora")
    other = await create_user(db)
    now = datetime.now(TZ)
    next_monday = (now + timedelta(days=7 - now.weekday())).replace(hour=10, minute=0)
    await award_points(db, user_id=reader.id, amount=25, category=ScoreCategory.ATTENDANCE, idempotency_key="d1")
    await create_event(db, title="Navbatdagi kecha", starts_at=next_monday + timedelta(days=2))
    await db.commit()
    await premium_service.grant(db, actor_id=admin.id, user_id=reader.id, days=30, note=None)

    assert await feedback_service.weekly_digest(db, now=next_monday.replace(hour=8)) == 0
    assert await feedback_service.weekly_digest(db, now=next_monday + timedelta(days=1)) == 0
    # Premium only by default: the reader and the super admin (Premium for life).
    assert await feedback_service.weekly_digest(db, now=next_monday) == 2
    await feedback_service.weekly_digest(db, now=next_monday)
    await db.commit()
    digests = list(
        await db.scalars(
            select(Notification).where(Notification.type == NotificationType.DIGEST, Notification.user_id == reader.id)
        )
    )
    assert len(digests) == 1 and other.id != reader.id
    assert "Haftalik xulosangiz" in digests[0].text and "«Navbatdagi kecha»" in digests[0].text

    await _set(db, admin, "weekly_digest", FeatureMode.ALL)
    later = next_monday + timedelta(days=7)
    assert await feedback_service.weekly_digest(db, now=later) == 3  # everyone, including the admin
    del other


# ---------------------------------------------------------------------------- reports


async def test_period_and_general_reports(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _super_admin(db)
    member = await create_user(db, first_name="Laylo", last_name="Rahimova")
    event = await create_event(db, title="Oktabr kechasi")
    db.add(AttendanceRecord(event_id=event.id, user_id=member.id, method=AttendanceMethod.CODE))
    await award_points(db, user_id=member.id, amount=30, category=ScoreCategory.ATTENDANCE, idempotency_key="r1")
    await db.commit()
    headers = admin_headers(admin)
    today = datetime.now(TZ).date()
    start = today.replace(day=1)

    created = await client.post(
        "/api/v1/admin/reports",
        json={"kind": "PERIOD", "period_start": start.isoformat(), "period_end": today.isoformat()},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["kind"] == "PERIOD" and report["event_id"] is None
    summary = report["facts"]["summary"]
    assert summary["events"] == 1 and summary["attendances"] == 1 and summary["participants"] == 1
    assert report["facts"]["top_members"][0]["name"] == "Rahimova Laylo"
    assert "faoliyat hisoboti" in report["title"]

    drafted = await client.post(
        f"/api/v1/admin/reports/{report['id']}/generate", json={"use_ai": False}, headers=headers
    )
    body = drafted.json()["body_text"]
    assert "## Tadbirlar" in body and "«Oktabr kechasi»" in body and drafted.json()["number_issues"] == []
    approved = await client.post(f"/api/v1/admin/reports/{report['id']}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    pdf = await client.get(f"/api/v1/admin/reports/{report['id']}/pdf", headers=headers)
    assert pdf.content.startswith(b"%PDF")

    bad = await client.post(
        "/api/v1/admin/reports",
        json={"kind": "PERIOD", "period_start": today.isoformat(), "period_end": start.isoformat()},
        headers=headers,
    )
    assert bad.status_code == 400 or start == today
    untitled = await client.post("/api/v1/admin/reports", json={"kind": "GENERAL"}, headers=headers)
    assert untitled.status_code == 400 and untitled.json()["error"]["code"] == "TITLE_REQUIRED"
    general = await client.post(
        "/api/v1/admin/reports", json={"kind": "GENERAL", "title": "Kutubxonaga kitob topshirish"}, headers=headers
    )
    general_id = general.json()["id"]
    await client.patch(
        f"/api/v1/admin/reports/{general_id}",
        json={"objective": "Kutubxona fondini boyitish.", "activity_description": "A'zolar 40 ta kitob topshirdi."},
        headers=headers,
    )
    drafted = await client.post(f"/api/v1/admin/reports/{general_id}/generate", json={"use_ai": False}, headers=headers)
    assert "## Amalga oshirilgan ishlar" in drafted.json()["body_text"]
    assert (await client.post(f"/api/v1/admin/reports/{general_id}/approve", headers=headers)).status_code == 200
    copy = await client.post(f"/api/v1/admin/reports/{general_id}/new-version", headers=headers)
    assert copy.json()["version"] == 2 and copy.json()["kind"] == "GENERAL"

    listed = (await client.get("/api/v1/admin/reports", headers=headers)).json()["items"]
    subjects = {item["kind"]: item["event_title"] for item in listed}
    assert subjects["GENERAL"] == "Umumiy hisobot" and "gacha" in subjects["PERIOD"]
    no_event = await client.post("/api/v1/admin/reports", json={"kind": "EVENT"}, headers=headers)
    assert no_event.status_code == 404


async def test_payment_kinds_parse() -> None:
    assert premium_service.parse_payload("donation:50:" + "a" * 32 + ":deadbeef").kind == PaymentKind.DONATION
    assert premium_service.parse_payload("premium:50:" + "a" * 32 + ":deadbeef") is None
    assert premium_service.parse_payload("donation:" + "b" * 32 + ":" + "a" * 32 + ":deadbeef") is None
    assert premium_service.parse_payload("") is None
