"""Phase 23: first deployment by a non-programmer. Values pasted with extra text must still work,
a bad bot token must not take the whole server down, and real problems must be explained in
plain words in the hosting platform's log."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.bot import setup as bot_setup
from app.cli import preflight
from app.core.config import Settings, get_settings
from app.services import system_status

TOKEN = "123456789:AAFakeTokenForDeploymentTests_abcdefghij"
BACKEND = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "pasted",
    [
        f"{TOKEN} ",
        f"{TOKEN}\n",
        f"Use this token to access the HTTP API:\n{TOKEN}\nKeep your token secure",
    ],
)
def test_bot_token_is_taken_out_of_pasted_text(pasted: str) -> None:
    settings = Settings(_env_file=None, bot_token=pasted)
    assert settings.bot_token is not None and settings.bot_token.get_secret_value() == TOKEN


@pytest.mark.parametrize(
    "pasted",
    [
        "psql 'postgresql://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'",
        "'postgresql://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'",
        "  postgresql://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require\n",
    ],
)
def test_database_url_is_taken_out_of_pasted_text(pasted: str) -> None:
    settings = Settings(_env_file=None, database_url=pasted)
    url, connect_args = settings.sqlalchemy_database
    assert url == "postgresql+asyncpg://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/neondb"
    assert connect_args == {"ssl": "require"}


def test_super_admin_ids_ignore_placeholders_and_names() -> None:
    assert Settings(_env_file=None, super_admin_telegram_ids="0").super_admin_telegram_ids == []
    assert Settings(_env_file=None, super_admin_telegram_ids="@akmaljon").super_admin_telegram_ids == []
    ids = Settings(_env_file=None, super_admin_telegram_ids="123 456, 789;0").super_admin_telegram_ids
    assert ids == [123, 456, 789]


def test_production_requires_a_database_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL is not set"):
        Settings(_env_file=None, environment="production", secret_key="x" * 44)
    with pytest.raises(ValueError, match="DATABASE_URL is empty"):
        Settings(_env_file=None, database_url="   ")


def test_preflight_explains_problems_in_uzbek(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "short")
    monkeypatch.setenv("DATABASE_URL", "mysql://u:p@h/db")
    assert preflight() == 1
    err = capsys.readouterr().err
    assert "server ishga tushmadi" in err
    assert "DATABASE_URL noto'g'ri" in err and "SECRET_KEY kamida 32" in err
    assert "u:p@h" not in err  # values are never printed

    monkeypatch.setenv("SECRET_KEY", "x" * 44)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    assert preflight() == 0


def test_start_script_stops_with_an_explanation(tmp_path: Path) -> None:
    env = {
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(tmp_path),
        "ENVIRONMENT": "production",
        "SECRET_KEY": "x" * 44,
    }
    result = subprocess.run(
        ["/bin/sh", "start.sh"], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 1
    assert "DATABASE_URL noto'g'ri yoki kiritilmagan" in result.stderr
    assert "alembic" not in result.stdout + result.stderr  # stopped before touching the database


async def test_invalid_bot_token_disables_only_the_bot(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, db
) -> None:
    settings = get_settings().model_copy(update={"bot_token": Settings(_env_file=None, bot_token="my bot").bot_token})
    monkeypatch.setattr(bot_setup, "get_settings", lambda: settings)
    monkeypatch.setattr(system_status, "get_settings", lambda: settings)
    monkeypatch.setattr(bot_setup, "_runtime", None)
    monkeypatch.setattr(bot_setup, "_reported_invalid_token", False)

    with caplog.at_level(logging.ERROR):
        assert bot_setup.get_bot_runtime() is None
        assert bot_setup.get_bot_runtime() is None
    assert [r.getMessage() for r in caplog.records].count(
        "BOT_TOKEN is not a valid Telegram bot token; the bot is disabled until it is fixed"
    ) == 1

    checks = {check["key"]: check for check in (await system_status.collect(db))["checks"]}
    assert checks["bot"]["status"] == "error" and "BOT_TOKEN noto'g'ri" in checks["bot"]["detail"]
