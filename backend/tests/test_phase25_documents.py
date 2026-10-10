"""Kitobxon passport (ID card image) and certificates (PDF) with public QR verification."""

from __future__ import annotations

import dataclasses
import io
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import GetFile, GetUserProfilePhotos, SendDocument, SendPhoto
from aiogram.methods.base import TelegramMethod
from aiogram.types import File, PhotoSize, UserProfilePhotos
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import AttendanceRecord, Certificate, FeatureFlag, Notification, TestAttempt, User
from app.models.enums import (
    AttemptStatus,
    AttendanceMethod,
    CertificateKind,
    FeatureMode,
    NotificationStatus,
    NotificationType,
    ScoreCategory,
    TestStatus,
)
from app.security.permissions import Perm
from app.services import certificates as certificate_service
from app.services import downloads
from app.services import passport as passport_service
from app.services import quizzes as quiz_service
from app.services.scoring import award_points
from app.services.settings import update_setting
from app.workers import sender as sender_module
from app.workers.sender import send_due_notifications
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

sender_module.SEND_INTERVAL_SECONDS = 0
BASE = "https://kitobxon.example.org"


@pytest.fixture(autouse=True)
async def _certificate_pdf_for_everyone(db: AsyncSession) -> None:
    """These tests are about the documents; the Premium lock on certificate PDFs is tested elsewhere."""
    db.add(FeatureFlag(code="certificate_pdf", mode=FeatureMode.ALL))
    await db.commit()


@pytest.fixture(autouse=True)
def _public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", BASE)
    # No real Telegram in tests; tests that need the bot install a fake one.
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


def _jpeg(color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 400), color).save(buffer, format="JPEG")
    return buffer.getvalue()


class PhotoTelegram(FakeTelegramSession):
    """Fake Telegram that knows the member's profile photo and can refuse to send."""

    def __init__(self, *, blocked: bool = False) -> None:
        super().__init__()
        self.blocked = blocked
        self.downloads = 0

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, GetUserProfilePhotos):
            self.requests.append(method)
            sizes = [
                PhotoSize(file_id="small", file_unique_id="u-small", width=160, height=160),
                PhotoSize(file_id="big", file_unique_id="u-big", width=640, height=640),
            ]
            return UserProfilePhotos(total_count=1, photos=[sizes])
        if isinstance(method, GetFile):
            self.requests.append(method)
            return File(file_id=method.file_id, file_unique_id="u-big", file_path="photos/big.jpg")
        if self.blocked and isinstance(method, SendDocument):
            raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")
        return await super().make_request(bot, method, timeout)

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        self.downloads += 1
        yield _jpeg((180, 40, 40))


def _install_bot(monkeypatch: pytest.MonkeyPatch, telegram: FakeTelegramSession) -> Bot:
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: SimpleNamespace(bot=bot))
    return bot


async def _attempt(db: AsyncSession, test_id: Any, user: User, score: int, minutes: int = 5) -> None:
    started = datetime.now(UTC) - timedelta(minutes=30)
    db.add(
        TestAttempt(
            test_id=test_id,
            user_id=user.id,
            status=AttemptStatus.SUBMITTED,
            started_at=started,
            deadline_at=started + timedelta(minutes=15),
            submitted_at=started + timedelta(minutes=minutes),
            question_order=[],
            option_order={},
            correct_count=score,
            raw_score=score,
            raw_max=20,
            score=score,
        )
    )
    await db.flush()


async def _manager(db: AsyncSession) -> User:
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.REWARD_MANAGE)
    return admin


# ---------------------------------------------------------------------------- passport


async def test_passport_image_and_member_number(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, first_name="Malika", last_name="Abdurahmonova", group_name="214")
    await award_points(db, user_id=member.id, amount=40, category=ScoreCategory.ATTENDANCE, idempotency_key="p1")
    await db.commit()

    me = (await client.get("/api/v1/me", headers=member_headers(member))).json()
    assert me["member_number"] == passport_service.member_number(member)
    assert me["member_number"].startswith("KH-") and len(me["member_number"]) == 9

    response = await client.get("/api/v1/me/passport", headers=member_headers(member))
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"].startswith("inline;")
    image = Image.open(io.BytesIO(response.content))
    assert image.size == (passport_service.WIDTH, passport_service.HEIGHT)

    download = await client.get("/api/v1/me/passport?download=true", headers=member_headers(member))
    assert download.headers["content-disposition"].startswith("attachment;")
    assert (await client.get("/api/v1/me/passport")).status_code == 401

    data = await passport_service.collect(db, member)
    assert data.group_name == "214" and data.theme == "classic"
    assert data.verify_url == f"{BASE}/v/{passport_service.verify_code(member)}"
    results = await passport_service.live_results(db, member)  # shown behind the QR code, not on the card
    assert results["points"] == 40 and results["rank"] == 1


async def test_passport_drawing_handles_long_names_and_photos() -> None:
    photo = io.BytesIO()
    Image.new("RGB", (640, 640), (200, 30, 30)).save(photo, format="JPEG")
    data = passport_service.PassportData(
        number="KH-000001",
        first_name="Muhammadabdulloh",
        last_name="Abdurahmonova-Qodirova-Xo'jayeva",
        faculty="Tibbiy profilaktika va jamoat salomatligi (kechki ta'lim)",
        course=None,
        group_name=None,
        member_since="01.10.2026",
        verify_url=None,
        active=False,
    )
    for avatar in (photo.getvalue(), b"not an image", None):
        image = Image.open(io.BytesIO(passport_service.draw_passport(data, avatar)))
        assert image.size == (1200, 756)
    for theme in passport_service.THEMES:
        themed = dataclasses.replace(data, theme=theme, premium=True, active=True, verify_url="https://x.org/v/1")
        assert passport_service.draw_passport(themed).startswith(b"\x89PNG")


async def test_passport_qr_page_verifies_members(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, first_name="Malika", last_name="Karimova")
    await db.commit()
    code = passport_service.verify_code(member)

    page = await client.get(f"/v/{code}")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert "Karimova Malika" in page.text and "Haqiqiy" in page.text
    assert "style-src 'unsafe-inline'" in page.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "DENY"
    assert page.headers["cache-control"] == "no-store"

    forged = code[:-1] + ("0" if code[-1] != "0" else "1")
    missing = await client.get(f"/v/{forged}")
    assert missing.status_code == 404 and "Kod topilmadi" in missing.text and "Karimova" not in missing.text
    assert (await client.get("/v/<script>")).status_code == 404


async def test_bot_sends_the_passport_as_a_picture(db: AsyncSession) -> None:
    await create_user(db, telegram_id=7101, first_name="Aziza", group_name="402")
    await db.commit()
    harness = BotHarness(7101)

    await harness.send(texts.BTN_PASSPORT)
    photo = next(r for r in reversed(harness.session.requests) if isinstance(r, SendPhoto))
    assert "Aziza" in photo.caption and "KH-" in photo.caption and "402" in photo.caption
    buttons = [b.callback_data or b.text for row in photo.reply_markup.inline_keyboard for b in row]
    assert "pp:file" in buttons and texts.BTN_CERTIFICATES in buttons  # certificates open in the Mini App

    await harness.press("pp:file")
    document = next(r for r in reversed(harness.session.requests) if isinstance(r, SendDocument))
    assert document.document.filename.startswith("kitobxon-pasporti-KH-")
    assert harness.session.alerts()[-1] == texts.FILE_SENT

    await harness.press("cert:list")  # a button of an older message
    assert harness.last_text() == texts.CERTIFICATES_IN_APP


async def test_bot_falls_back_to_text_when_drawing_fails(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    await create_user(db, telegram_id=7102, first_name="Jasur")
    await db.commit()

    async def broken(*args: Any, **kwargs: Any) -> bytes:
        raise RuntimeError("no fonts")

    monkeypatch.setattr(passport_service, "render", broken)
    harness = BotHarness(7102)
    await harness.send(texts.BTN_PASSPORT)
    assert "Jasur" in harness.last_text()
    await harness.press("pp:file")
    assert harness.session.alerts()[-1] == texts.FILE_FAILED


# ---------------------------------------------------------------------------- certificates


async def test_test_winners_get_certificates_seen_in_the_app(db: AsyncSession) -> None:
    members = [await create_user(db, telegram_id=7200 + i, first_name=f"Golib{i}") for i in range(5)]
    test = await create_test(db, title="O'tkan kunlar")
    test_id = test.id
    for score, member in zip((20, 18, 15, 12, 4), members, strict=True):
        await _attempt(db, test_id, member, score)
    await db.commit()

    await quiz_service.close_test(db, actor_id=None, test_id=test_id)
    certificates = list(await db.scalars(select(Certificate).order_by(Certificate.place)))
    assert [(c.user_id, c.place, c.kind) for c in certificates] == [
        (members[0].id, 1, CertificateKind.TEST_PLACE),
        (members[1].id, 2, CertificateKind.TEST_PLACE),
        (members[2].id, 3, CertificateKind.TEST_PLACE),
    ]
    assert certificates[0].title == "«O'tkan kunlar» testi — 1-o'rin"
    assert "1-o'rinni egallagani uchun" in certificates[0].description

    # Closing again (e.g. the scheduler) issues nothing new.
    await quiz_service.close_test(db, actor_id=None, test_id=test_id)
    assert await db.scalar(select(func.count()).select_from(Certificate)) == 3

    notification = await db.scalar(
        select(Notification).where(
            Notification.type == NotificationType.CERTIFICATE, Notification.user_id == members[0].id
        )
    )
    assert "certificate_id" not in notification.payload  # no PDF in the bot: it is seen in the app
    assert {"text": "🎓 Sertifikatni ko'rish", "app_route": f"certificates/{certificates[0].id}"} in (
        notification.payload["buttons"]
    )
    assert "Tabriklaymiz" in notification.text and "1-o'rin" in notification.text
    assert len({c.design for c in certificates}) == 1  # one test, one design

    telegram = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await send_due_notifications(get_session_factory(), bot)
    assert not [r for r in telegram.requests if isinstance(r, SendDocument)]
    assert {m.chat_id for m in telegram.sent_messages()} >= {7200, 7201, 7202}


async def test_event_test_counts_only_members_who_attended(db: AsyncSession) -> None:
    present = [await create_user(db) for _ in range(2)]
    absent = await create_user(db)
    event = await create_event(db, title="Kitob kechasi")
    test = await create_test(db, title="Kecha savollari", event_id=event.id)
    test_id = test.id
    for member in present:
        db.add(AttendanceRecord(event_id=event.id, user_id=member.id, method=AttendanceMethod.CODE))
    await _attempt(db, test_id, absent, 20)  # best score, but did not attend
    await _attempt(db, test_id, present[0], 15)
    await _attempt(db, test_id, present[1], 12)
    await db.commit()

    await quiz_service.close_test(db, actor_id=None, test_id=test_id)
    rows = (await db.execute(select(Certificate.user_id, Certificate.place).order_by(Certificate.place))).all()
    assert rows == [(present[0].id, 1), (present[1].id, 2)]
    description = await db.scalar(select(Certificate.description).where(Certificate.place == 1))
    assert "«Kitob kechasi» tadbiri doirasida" in description


async def test_test_certificates_can_be_switched_off(db: AsyncSession) -> None:
    member = await create_user(db)
    test = await create_test(db)
    await _attempt(db, test.id, member, 20)
    await update_setting(db, key="certificates.test_winners", value=False, actor_id=member.id)
    await db.commit()
    await quiz_service.close_test(db, actor_id=None, test_id=test.id)
    assert await db.scalar(select(func.count()).select_from(Certificate)) == 0


async def test_monthly_top_three_get_certificates(db: AsyncSession) -> None:
    members = [await create_user(db) for _ in range(4)]
    for amount, member in zip((50, 40, 30, 20), members, strict=True):
        await award_points(
            db, user_id=member.id, amount=amount, category=ScoreCategory.ATTENDANCE, idempotency_key=f"m{amount}"
        )
    await db.commit()
    tz = ZoneInfo(get_settings().timezone)
    this_month = datetime.now(tz).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (this_month + timedelta(days=32)).replace(day=1)

    # Not before 10:00 on the 1st, not after the first week, never before the feature started.
    assert await certificate_service.issue_monthly(db, now=next_month.replace(hour=9)) == 0
    assert await certificate_service.issue_monthly(db, now=next_month.replace(day=8, hour=12)) == 0
    assert await certificate_service.issue_monthly(db, now=datetime(2026, 10, 2, 12, tzinfo=tz)) == 0

    assert await certificate_service.issue_monthly(db, now=next_month.replace(day=2, hour=12)) == 3
    assert await certificate_service.issue_monthly(db, now=next_month.replace(day=3, hour=12)) == 0
    await db.commit()
    rows = (await db.execute(select(Certificate).order_by(Certificate.place))).scalars().all()
    assert [(c.user_id, c.place, c.kind) for c in rows] == [
        (members[0].id, 1, CertificateKind.MONTHLY_TOP),
        (members[1].id, 2, CertificateKind.MONTHLY_TOP),
        (members[2].id, 3, CertificateKind.MONTHLY_TOP),
    ]
    assert rows[0].period == f"{this_month:%Y-%m}" and "reytingi — 1-o'rin" in rows[0].title


async def test_admin_issues_and_revokes_certificates(client: httpx.AsyncClient, db: AsyncSession) -> None:
    manager = await _manager(db)
    member = await create_user(db, first_name="Dilnoza", last_name="Yusupova")
    other = await create_user(db)
    plain_admin = await create_user(db)
    await db.commit()
    await grant_role(db, plain_admin, "ADMIN")

    body = {
        "user_id": str(member.id),
        "title": "Faol kitobxon",
        "description": "Klub faoliyatida faol ishtirok etgani uchun taqdim etiladi.",
    }
    assert (
        await client.post("/api/v1/admin/certificates", json=body, headers=admin_headers(plain_admin))
    ).status_code == 403
    created = await client.post("/api/v1/admin/certificates", json=body, headers=admin_headers(manager))
    assert created.status_code == 201, created.text
    certificate = created.json()
    assert certificate["kind"] == "MANUAL" and certificate["place"] is None
    assert certificate["member"]["last_name"] == "Yusupova" and len(certificate["code"]) == 11

    listed = await client.get("/api/v1/admin/certificates?q=Yusupova", headers=admin_headers(manager))
    assert listed.json()["total"] == 1
    by_code = await client.get(f"/api/v1/admin/certificates?q={certificate['code']}", headers=admin_headers(manager))
    assert by_code.json()["total"] == 1
    pdf = await client.get(f"/api/v1/admin/certificates/{certificate['id']}/pdf", headers=admin_headers(manager))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # The member sees and downloads it; nobody else can.
    mine = await client.get("/api/v1/me/certificates", headers=member_headers(member))
    assert [c["title"] for c in mine.json()] == ["Faol kitobxon"]
    own_pdf = await client.get(f"/api/v1/me/certificates/{certificate['id']}/pdf", headers=member_headers(member))
    assert own_pdf.status_code == 200 and own_pdf.headers["content-type"] == "application/pdf"
    stolen = await client.get(f"/api/v1/me/certificates/{certificate['id']}/pdf", headers=member_headers(other))
    assert stolen.status_code == 404

    page = await client.get(f"/v/{certificate['code']}")
    assert page.status_code == 200 and "Haqiqiy sertifikat" in page.text and "Yusupova Dilnoza" in page.text
    lower = await client.get(f"/v/{certificate['code'].lower().replace('-', '')}")
    assert lower.status_code == 200

    revoked = await client.post(
        f"/api/v1/admin/certificates/{certificate['id']}/revoke",
        json={"reason": "Xato bilan berilgan"},
        headers=admin_headers(manager),
    )
    assert revoked.status_code == 200 and revoked.json()["revoked_at"]
    again = await client.post(
        f"/api/v1/admin/certificates/{certificate['id']}/revoke",
        json={"reason": "Xato bilan berilgan"},
        headers=admin_headers(manager),
    )
    assert again.status_code == 409
    assert (await client.get("/api/v1/me/certificates", headers=member_headers(member))).json() == []
    page = await client.get(f"/v/{certificate['code']}")
    assert "Bekor qilingan" in page.text
    stamped = await client.get(f"/api/v1/admin/certificates/{certificate['id']}/pdf", headers=admin_headers(manager))
    assert stamped.content.startswith(b"%PDF")

    notification = await db.scalar(select(Notification).where(Notification.user_id == member.id))
    assert notification.type == NotificationType.CERTIFICATE and notification.status == NotificationStatus.PENDING

    unknown = await client.post(
        "/api/v1/admin/certificates",
        json={**body, "user_id": str(manager.id)[:-1] + "0"},
        headers=admin_headers(manager),
    )
    assert unknown.status_code == 404


async def test_bot_points_certificates_to_the_app(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=7301)
    certificate = await certificate_service.issue(
        db,
        user_id=member.id,
        kind=CertificateKind.MANUAL,
        title="Eng yaxshi taqriz",
        description="Eng yaxshi kitob taqrizi uchun taqdim etiladi.",
        dedup_key="manual:test",
    )
    await db.commit()
    harness = BotHarness(7301)

    await harness.send(texts.BTN_ACHIEVEMENTS)
    assert "🎓 Sertifikatlar: 1" in harness.last_text()
    # Buttons of older messages now lead to the Mini App, where certificates are seen and downloaded.
    for data in ("cert:list", f"cert:get:{certificate.id}", "cert:get:not-a-uuid"):
        await harness.press(data)
        message = harness.session.sent_messages()[-1]
        assert message.text == texts.CERTIFICATES_IN_APP
        assert message.reply_markup.inline_keyboard[0][0].web_app is not None
    assert not any(isinstance(r, SendDocument) for r in harness.session.requests)


# ---------------------------------------------------------------------------- download links


async def test_download_links_work_without_sign_in_for_five_minutes(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    member = await create_user(db)
    other = await create_user(db)
    certificate = await certificate_service.issue(
        db,
        user_id=member.id,
        kind=CertificateKind.MANUAL,
        title="Faol a'zo",
        description="Faolligi uchun taqdim etiladi.",
        dedup_key="manual:link",
    )
    await db.commit()

    link = await client.post("/api/v1/me/downloads", json={"kind": "passport"}, headers=member_headers(member))
    assert link.status_code == 200 and link.json()["url"].startswith(f"{BASE}/api/v1/files/")
    image = await client.get(link.json()["url"].removeprefix(BASE))
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.headers["content-disposition"].startswith("attachment;")

    cert_link = await client.post(
        "/api/v1/me/downloads", json={"kind": "certificate", "id": str(certificate.id)}, headers=member_headers(member)
    )
    pdf = await client.get(cert_link.json()["url"].removeprefix(BASE))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    foreign = await client.post(
        "/api/v1/me/downloads", json={"kind": "certificate", "id": str(certificate.id)}, headers=member_headers(other)
    )
    assert foreign.status_code == 404

    token = cert_link.json()["url"].rsplit("/", 1)[1]
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert (await client.get(f"/api/v1/files/{tampered}")).status_code == 404
    assert (await client.get("/api/v1/files/passport.x.y.z")).status_code == 404
    old = downloads.make_token("passport", member.id, now=datetime.now(UTC).timestamp() - 400)
    expired = await client.get(f"/api/v1/files/{old}")
    assert expired.status_code == 404 and expired.json()["error"]["code"] == "LINK_EXPIRED"


async def test_send_to_bot_needs_a_running_bot(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    response = await client.post("/api/v1/me/passport/send", headers=member_headers(member))
    assert response.status_code == 503 and response.json()["error"]["code"] == "BOT_UNAVAILABLE"


async def test_bot_sends_files_with_the_members_photo(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    member = await create_user(db, telegram_id=7401)
    certificate = await certificate_service.issue(
        db,
        user_id=member.id,
        kind=CertificateKind.MANUAL,
        title="Faol a'zo",
        description="Faolligi uchun taqdim etiladi.",
        dedup_key="manual:send",
    )
    await db.commit()
    telegram = PhotoTelegram()
    _install_bot(monkeypatch, telegram)

    sent = await client.post("/api/v1/me/passport/send", headers=member_headers(member))
    assert sent.status_code == 204
    document = next(r for r in telegram.requests if isinstance(r, SendDocument))
    assert document.chat_id == 7401 and document.document.filename.endswith(".png")
    # The larger photo was chosen, downloaded once and then served from storage.
    assert next(r for r in telegram.requests if isinstance(r, GetFile)).file_id == "big"
    assert (await client.get("/api/v1/me/passport", headers=member_headers(member))).status_code == 200
    assert telegram.downloads == 1

    sent = await client.post(f"/api/v1/me/certificates/{certificate.id}/send", headers=member_headers(member))
    assert sent.status_code == 204
    assert [r for r in telegram.requests if isinstance(r, SendDocument)][-1].document.filename.endswith(".pdf")

    _install_bot(monkeypatch, PhotoTelegram(blocked=True))
    refused = await client.post("/api/v1/me/passport/send", headers=member_headers(member))
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "BOT_BLOCKED"


async def test_certificate_pdf_is_redrawn_when_the_file_is_lost(db: AsyncSession) -> None:
    member = await create_user(db)
    test = await create_test(db, status=TestStatus.CLOSED)
    certificate = await certificate_service.issue(
        db,
        user_id=member.id,
        kind=CertificateKind.TEST_PLACE,
        place=2,
        title="Test — 2-o'rin",
        description="Testda 2-o'rinni egallagani uchun taqdim etiladi.",
        dedup_key="test:lost",
        test_id=test.id,
    )
    certificate.file_key = "certificates/missing.pdf"
    data = await certificate_service.pdf_bytes(db, certificate)
    assert data.startswith(b"%PDF")
    assert certificate.file_key == f"certificates/{certificate.id}-{certificate.design}.pdf"
