"""Phase 21: security hardening — headers, body limits, per-member limits, safe exports,
image bombs, log redaction and production defaults."""

from __future__ import annotations

import io
import logging
import struct
import zlib
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import BadRequestError
from app.core.logging import RedactingFilter, redact
from app.core.security_headers import ADMIN_CSP, MAX_JSON_BYTES, MINIAPP_CSP, headers_for
from app.models import Notification, NotificationTemplate, User
from app.models.enums import NotificationType
from app.security.permissions import Perm
from app.security.rate_limit import RateLimit
from app.services.reports import _process_photo
from app.utils.spreadsheet import excel_writer, safe_cell
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


# ---------------------------------------------------------------------------- headers


async def test_api_responses_carry_security_headers(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    response = await client.get("/api/v1/me", headers=member_headers(member))
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers  # only in production
    # Error responses get them too.
    missing = await client.get("/api/v1/no-such-route")
    assert missing.headers["X-Frame-Options"] == "DENY"


def test_header_policy_per_area() -> None:
    admin = headers_for("/admin/assets/index.js", production=True)
    assert admin["Content-Security-Policy"] == ADMIN_CSP
    assert admin["X-Frame-Options"] == "DENY"
    assert admin["Strict-Transport-Security"].startswith("max-age=")
    # Telegram Web shows the Mini App in an iframe, so it must stay embeddable.
    miniapp = headers_for("/app/", production=True)
    assert miniapp["Content-Security-Policy"] == MINIAPP_CSP
    assert "X-Frame-Options" not in miniapp and "frame-ancestors" not in MINIAPP_CSP
    assert "https://telegram.org" in MINIAPP_CSP and "'unsafe-eval'" not in MINIAPP_CSP
    assert "script-src 'self';" in ADMIN_CSP  # no third-party scripts in the admin panel
    assert "Cache-Control" not in miniapp  # static files may be cached


# ---------------------------------------------------------------------------- body limits


async def test_oversized_bodies_are_rejected(client: httpx.AsyncClient) -> None:
    big = b'{"init_data": "' + b"a" * (MAX_JSON_BYTES + 10) + b'"}'
    declared = await client.post("/api/v1/auth/telegram", content=big, headers={"Content-Type": "application/json"})
    assert declared.status_code == 413
    assert declared.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    async def chunks() -> AsyncIterator[bytes]:
        for start in range(0, len(big), 512 * 1024):
            yield big[start : start + 512 * 1024]

    streamed = await client.post(
        "/api/v1/auth/telegram", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert streamed.status_code == 413
    assert streamed.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


# ---------------------------------------------------------------------------- per-member limit


async def test_each_member_has_an_api_budget(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.deps.USER_API_LIMIT", RateLimit("api-user-test", limit=3, window_seconds=60))
    member, other = await create_user(db), await create_user(db)
    await db.commit()
    statuses = [(await client.get("/api/v1/me", headers=member_headers(member))).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]
    # Another member is not affected.
    assert (await client.get("/api/v1/me", headers=member_headers(other))).status_code == 200


# ---------------------------------------------------------------------------- exports and messages


def test_csv_cells_cannot_become_formulas() -> None:
    assert safe_cell('=HYPERLINK("http://x")') == '\'=HYPERLINK("http://x")'
    assert safe_cell("+998") == "'+998"
    assert safe_cell("@SUM(A1)") == "'@SUM(A1)"
    assert safe_cell("Aliyev") == "Aliyev"
    assert safe_cell(-5) == -5  # numbers stay numbers
    buffer = io.StringIO()
    excel_writer(buffer).writerow(["-cmd", "Pediatriya", 3])
    assert buffer.getvalue().strip() == "'-cmd;Pediatriya;3"


async def test_broadcast_without_template_is_escaped(client: httpx.AsyncClient, db: AsyncSession) -> None:
    sender = await _admin(db, Perm.NOTIFICATION_SEND)
    await create_user(db)
    await db.execute(
        update(NotificationTemplate)
        .where(NotificationTemplate.type == NotificationType.ADMIN_MESSAGE)
        .values(is_active=False)
    )
    await db.commit()
    response = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"message": "Yig'ilish <b>15:00</b> da & 2<3"},
        headers=admin_headers(sender),
    )
    assert response.status_code == 200, response.text
    texts = set(await db.scalars(select(Notification.text).where(Notification.type == NotificationType.ADMIN_MESSAGE)))
    assert texts == {"Yig'ilish &lt;b&gt;15:00&lt;/b&gt; da &amp; 2&lt;3"}


# ---------------------------------------------------------------------------- uploads


def _png_header(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def test_image_bombs_are_refused_before_decoding() -> None:
    with pytest.raises(BadRequestError) as error:
        _process_photo(_png_header(20_000, 20_000))  # 400 megapixels in a few bytes
    assert error.value.code in {"PHOTO_TOO_LARGE", "PHOTO_INVALID"}
    with pytest.raises(BadRequestError):
        _process_photo(b"not an image at all")


# ---------------------------------------------------------------------------- logs and config


def test_logs_do_not_keep_personal_data() -> None:
    line = 'duplicate key value violates unique constraint "uq_users_phone" DETAIL: Key (phone)=(+998901234567)'
    assert "+998901234567" not in redact(line)
    assert "Key (phone)=([REDACTED])" in redact(line)
    assert redact("Qo'ng'iroq: +998 90 123 45 67") == "Qo'ng'iroq: [REDACTED_PHONE]"
    record = logging.LogRecord("x", logging.ERROR, "", 0, "phone %s", ("998901234567",), None)
    RedactingFilter().filter(record)
    assert "998901234567" not in record.getMessage()


def test_production_hides_api_docs_by_default() -> None:
    secret = "a-very-long-production-secret-value-0123456789"
    assert Settings(environment="production", secret_key=secret).api_docs_enabled is False
    assert Settings(environment="production", secret_key=secret, api_docs_enabled=True).api_docs_enabled is True
    assert Settings(environment="development").api_docs_enabled is True
    with pytest.raises(ValueError):
        Settings(environment="production", secret_key="short")
