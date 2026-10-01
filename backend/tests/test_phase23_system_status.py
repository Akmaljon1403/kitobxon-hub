"""Phase 23: production readiness checks for the owner (Admin Panel) and developers (CLI)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Notification, User
from app.models.enums import NotificationStatus, NotificationType
from app.security.permissions import Perm
from app.services import system_status
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

WEBHOOK = "https://kitobxon.example.uz/telegram/webhook"


def _fake_telegram(monkeypatch: pytest.MonkeyPatch, **info: Any) -> None:
    async def get_webhook_info() -> Any:
        if "error" in info:
            raise info["error"]
        defaults = {"url": WEBHOOK, "last_error_date": None, "last_error_message": None, "pending_update_count": 0}
        return SimpleNamespace(**{**defaults, **info})

    runtime = SimpleNamespace(bot=SimpleNamespace(get_webhook_info=get_webhook_info), username="kitobxon_test_bot")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: runtime)


def _with_settings(monkeypatch: pytest.MonkeyPatch, **values: Any) -> None:
    settings = get_settings().model_copy(update=values)
    monkeypatch.setattr(system_status, "get_settings", lambda: settings)
    monkeypatch.setattr("app.bot.setup.get_settings", lambda: settings, raising=False)


def _by_key(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {check["key"]: check for check in result["checks"]}


async def _owner(db: AsyncSession) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "SUPER_ADMIN")
    return user


async def test_status_needs_settings_permission_and_hides_secrets(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_telegram(monkeypatch)
    viewer = await create_user(db)
    await db.commit()
    await grant_role(db, viewer, "ADMIN")
    await grant_permissions(db, viewer, Perm.USER_VIEW)
    owner = await _owner(db)

    denied = await client.get("/api/v1/admin/system/status", headers=admin_headers(viewer))
    assert denied.status_code == 403
    response = await client.get("/api/v1/admin/system/status", headers=admin_headers(owner))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"] in {"ok", "warning", "error"}
    assert {"database", "bot", "storage", "worker", "owners", "ai", "public_url"} <= set(_by_key(body))
    for secret in (get_settings().bot_token, get_settings().secret_key):
        assert secret is not None and secret.get_secret_value() not in response.text


async def test_healthy_production_setup(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_telegram(monkeypatch)
    _with_settings(
        monkeypatch, public_base_url="https://kitobxon.example.uz", worker_enabled=True, environment="production"
    )
    await _owner(db)
    await _owner(db)
    checks = _by_key(await system_status.collect(db))
    assert checks["database"]["status"] == "ok"  # migrations are at head
    assert checks["bot"]["status"] == "ok" and "@kitobxon_test_bot" in checks["bot"]["detail"]
    assert checks["public_url"]["status"] == "ok"
    assert checks["worker"]["status"] == "ok"
    assert checks["owners"]["status"] == "ok"
    assert checks["ai"]["status"] == "info"  # optional
    # Files on the server disk are lost on rebuild: the owner is told to connect R2.
    assert checks["storage"]["status"] == "warning" and "R2" in checks["storage"]["detail"]


async def test_problems_are_explained(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_settings(monkeypatch, public_base_url=None, worker_enabled=True)
    _fake_telegram(monkeypatch, url="")
    db.add(
        Notification(
            user_id=(await create_user(db)).id,
            type=NotificationType.ADMIN_MESSAGE,
            text="Salom",
            status=NotificationStatus.PENDING,
            scheduled_at=datetime.now(UTC) - timedelta(hours=3),
        )
    )
    await db.commit()
    result = await system_status.collect(db)
    checks = _by_key(result)
    assert result["summary"] == "error"
    assert checks["public_url"]["status"] == "error" and "PUBLIC_BASE_URL" in checks["public_url"]["detail"]
    assert checks["bot"]["status"] == "error"  # webhook not registered
    assert checks["owners"]["status"] == "error" and "SUPER_ADMIN_TELEGRAM_IDS" in checks["owners"]["detail"]
    assert checks["worker"]["status"] == "warning" and "1 ta xabar" in checks["worker"]["detail"]


async def test_telegram_errors_and_outages(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_settings(monkeypatch, public_base_url="https://kitobxon.example.uz")
    _fake_telegram(
        monkeypatch,
        last_error_date=datetime.now(UTC) - timedelta(minutes=20),
        last_error_message="Wrong response from the webhook: 502 Bad Gateway",
        pending_update_count=7,
    )
    bot = _by_key(await system_status.collect(db))["bot"]
    assert bot["status"] == "warning" and "502" in bot["detail"] and "7 ta" in bot["detail"]

    _fake_telegram(monkeypatch, error=TimeoutError())
    assert _by_key(await system_status.collect(db))["bot"]["status"] == "warning"

    _with_settings(monkeypatch, bot_token=None)
    assert _by_key(await system_status.collect(db))["bot"]["status"] == "error"


async def test_cli_check_prints_and_sets_exit_code(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app import cli

    async def fake_collect(_: Any) -> dict[str, Any]:
        return {
            "summary": "error",
            "checks": [
                {"key": "owners", "status": "error", "title": "Bosh administratorlar", "detail": "Hech kim yo'q."}
            ],
        }

    monkeypatch.setattr("app.services.system_status.collect", fake_collect)
    monkeypatch.setattr(cli, "dispose_engine", _noop)
    assert await cli._check() == 1
    assert "[FAIL] Bosh administratorlar: Hech kim yo'q." in capsys.readouterr().out


async def _noop() -> None:
    return None
