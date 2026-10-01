"""Production readiness checks, shown to the owner in the Admin Panel and printed by
``python -m app.cli check``. Every check explains in plain Uzbek what is wrong and what to do.
Nothing secret is ever included in the result."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Notification, Role, UserRole
from app.models.enums import NotificationStatus
from app.services.storage import LocalStorage, get_storage

logger = logging.getLogger(__name__)

Status = Literal["ok", "info", "warning", "error"]
_RANK: dict[str, int] = {"ok": 0, "info": 0, "warning": 1, "error": 2}
_TELEGRAM_TIMEOUT_SECONDS = 5
NEON_FREE_LIMIT_MB = 512


@dataclass
class Check:
    key: str
    status: Status
    title: str
    detail: str


def migration_head() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


async def _database(session: AsyncSession) -> list[Check]:
    current = await session.scalar(text("SELECT version_num FROM alembic_version"))
    head = await asyncio.to_thread(migration_head)
    checks = [
        Check("database", "ok", "Ma'lumotlar bazasi", f"Ishlayapti, tuzilma eng so'nggi versiyada ({current}).")
        if current == head
        else Check(
            "database",
            "error",
            "Ma'lumotlar bazasi",
            f"Tuzilma eski ({current}, kerak: {head}). Serverni qayta ishga tushiring — yangilanish o'zi bajariladi.",
        )
    ]
    size_mb = round(int(await session.scalar(text("SELECT pg_database_size(current_database())")) or 0) / 1048576)
    near_limit = size_mb > NEON_FREE_LIMIT_MB * 0.8
    checks.append(
        Check(
            "database_size",
            "warning" if near_limit else "info",
            "Baza hajmi",
            f"{size_mb} MB"
            + (" — bepul tarif chegarasiga yaqin (Neon: 0,5 GB). Tarifni oshirish kerak." if near_limit else "."),
        )
    )
    return checks


async def _telegram() -> list[Check]:
    from app.bot.setup import WEBHOOK_PATH, get_bot_runtime

    settings = get_settings()
    if settings.bot_token is None:
        return [Check("bot", "error", "Telegram bot", "BOT_TOKEN kiritilmagan — bot ishlamaydi.")]
    if settings.bot_mode != "webhook":
        return [Check("bot", "info", "Telegram bot", f"Rejim: {settings.bot_mode} (serverda odatda «webhook»).")]
    runtime = get_bot_runtime()
    expected = f"{settings.base_url.rstrip('/')}{WEBHOOK_PATH}" if settings.base_url else None
    try:
        async with asyncio.timeout(_TELEGRAM_TIMEOUT_SECONDS):
            info = await runtime.bot.get_webhook_info()  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning("Webhook check failed: %s", type(exc).__name__)
        return [
            Check("bot", "warning", "Telegram bot", "Telegram bilan hozir bog'lanib bo'lmadi — keyinroq tekshiring.")
        ]
    if not info.url or (expected and info.url != expected):
        return [
            Check(
                "bot",
                "error",
                "Telegram bot",
                "Webhook ro'yxatdan o'tmagan yoki boshqa manzilga ulangan. Serverni qayta ishga tushiring.",
            )
        ]
    last_error = info.last_error_date
    if last_error is not None and last_error.tzinfo is None:
        last_error = last_error.replace(tzinfo=UTC)
    recent_error = last_error is not None and last_error > datetime.now(UTC) - timedelta(hours=6)
    if recent_error:
        return [
            Check(
                "bot",
                "warning",
                "Telegram bot",
                f"So'nggi soatlarda Telegram xato qayd etgan: «{info.last_error_message}». "
                f"Navbatda {info.pending_update_count} ta xabar.",
            )
        ]
    username = f"@{runtime.username}" if runtime and runtime.username else "bot"  # type: ignore[union-attr]
    return [Check("bot", "ok", "Telegram bot", f"{username} xabarlarni qabul qilyapti.")]


def _public_url() -> Check:
    base = get_settings().base_url
    if not base:
        return Check(
            "public_url",
            "error",
            "Sayt manzili",
            "PUBLIC_BASE_URL kiritilmagan — Mini App, admin havolasi va webhook ishlamaydi.",
        )
    if not base.startswith("https://"):
        return Check("public_url", "warning", "Sayt manzili", f"{base} — Telegram uchun https:// manzil kerak.")
    return Check("public_url", "ok", "Sayt manzili", base)


async def _storage() -> Check:
    settings = get_settings()
    storage = get_storage()
    key = f"system/probe-{uuid.uuid4()}.txt"
    try:
        await storage.put(key, b"ok", "text/plain")
        assert await storage.get(key) == b"ok"
        await storage.delete(key)
    except Exception as exc:
        logger.warning("Storage check failed: %s", type(exc).__name__)
        return Check(
            "storage",
            "error",
            "Fayllar ombori",
            "Rasm va PDF fayllarni saqlab bo'lmayapti. STORAGE_* sozlamalarini tekshiring.",
        )
    if isinstance(storage, LocalStorage) and settings.is_production:
        return Check(
            "storage",
            "warning",
            "Fayllar ombori",
            "Rasmlar va PDF hisobotlar server diskida — server qayta yig'ilganda o'chib ketadi. "
            "Bepul Cloudflare R2 ulang (DEPLOYMENT.md, «Fayllar»).",
        )
    where = "server diski" if isinstance(storage, LocalStorage) else f"S3 ({settings.storage_bucket})"
    return Check("storage", "ok", "Fayllar ombori", f"Ishlayapti: {where}.")


def _ai() -> Check:
    settings = get_settings()
    if settings.ai_api_key is None:
        return Check(
            "ai", "info", "AI yordamchi", "Ulanmagan — hisobotlar shablon bo'yicha yoziladi (bu ham to'liq ishlaydi)."
        )
    return Check("ai", "ok", "AI yordamchi", f"Ulangan ({settings.ai_model}).")


async def _worker(session: AsyncSession) -> Check:
    settings = get_settings()
    if not settings.worker_enabled:
        return Check(
            "worker",
            "warning",
            "Xabarlar va eslatmalar",
            "Fon jarayoni bu serverda o'chirilgan (WORKER_ENABLED=false). "
            "Alohida worker ishlayotganiga ishonch hosil qiling.",
        )
    late = datetime.now(UTC) - timedelta(seconds=settings.worker_interval_seconds * 2 + 300)
    stuck = int(
        await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.status == NotificationStatus.PENDING, Notification.scheduled_at < late)
        )
        or 0
    )
    if stuck:
        return Check(
            "worker",
            "warning",
            "Xabarlar va eslatmalar",
            f"{stuck} ta xabar navbatda kechikmoqda. Server uxlab qolgan bo'lishi mumkin — UptimeRobot'ni tekshiring.",
        )
    minutes = settings.worker_interval_seconds // 60
    every = f"har {minutes} daqiqada" if minutes else f"har {settings.worker_interval_seconds} soniyada"
    return Check("worker", "ok", "Xabarlar va eslatmalar", f"Ishlayapti, eslatmalar {every} tekshiriladi.")


async def _owners(session: AsyncSession) -> Check:
    count = int(
        await session.scalar(
            select(func.count(func.distinct(UserRole.user_id)))
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.code == "SUPER_ADMIN")
        )
        or 0
    )
    if count == 0:
        return Check(
            "owners",
            "error",
            "Bosh administratorlar",
            "Hech kim yo'q. SUPER_ADMIN_TELEGRAM_IDS ga Telegram ID'ingizni yozing va botga /start yuboring.",
        )
    if count == 1:
        return Check(
            "owners",
            "info",
            "Bosh administratorlar",
            "Faqat bitta. Telegram akkaunt yo'qolsa ham kirish saqlanishi uchun ishonchli ikkinchi odamni tayinlang.",
        )
    return Check("owners", "ok", "Bosh administratorlar", f"{count} ta.")


def _environment() -> Check:
    settings = get_settings()
    if settings.is_production:
        return Check("environment", "ok", "Ish rejimi", f"production, versiya {settings.app_version}.")
    return Check(
        "environment", "info", "Ish rejimi", f"{settings.environment} (haqiqiy serverda «production» bo'lishi kerak)."
    )


async def collect(session: AsyncSession, *, check_telegram: bool = True) -> dict[str, Any]:
    checks: list[Check] = [_environment(), _public_url()]
    checks += await _database(session)
    if check_telegram:
        checks += await _telegram()
    checks += [await _storage(), await _worker(session), await _owners(session), _ai()]
    worst = max((check.status for check in checks), key=_RANK.__getitem__, default="ok")
    return {
        "summary": "ok" if _RANK[worst] == 0 else worst,
        "checked_at": datetime.now(UTC),
        "checks": [asdict(check) for check in checks],
    }
