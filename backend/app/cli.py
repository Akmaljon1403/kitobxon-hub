"""Maintenance commands.

python -m app.cli bootstrap    # (re)create permissions, system roles and default settings
python -m app.cli check        # production readiness checks (exit code 1 on errors)
python -m app.cli preflight    # validate the configuration before start-up (used by start.sh)
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.database import dispose_engine, get_session_factory
from app.core.logging import configure_logging
from app.services.bootstrap import sync_reference_data


async def _bootstrap() -> None:
    try:
        async with get_session_factory()() as session:
            await sync_reference_data(session)
    finally:
        await dispose_engine()
    print("Reference data is up to date.")


# What to tell the owner when a variable is wrong (printed to the hosting platform's log).
_HINTS = {
    "database_url": "DATABASE_URL noto'g'ri yoki kiritilmagan. Neon → Connect oynasidagi postgresql:// bilan "
    "boshlanadigan manzilni to'liq nusxalab, Render → Environment → DATABASE_URL ga qo'ying.",
    "secret_key": "SECRET_KEY kamida 32 belgidan iborat tasodifiy qiymat bo'lishi kerak. Render'da uni "
    "o'chirib, «Generate» tugmasi bilan yangisini yarating.",
    "bot_token": "BOT_TOKEN noto'g'ri. @BotFather bergan tokenni (123456789:AA... ko'rinishida) qayta nusxalang.",
    "storage_backend": "STORAGE_BACKEND faqat «local» yoki «s3» bo'lishi mumkin.",
    "storage_variables": "STORAGE_BACKEND=s3 uchun STORAGE_ENDPOINT, STORAGE_BUCKET, STORAGE_ACCESS_KEY va "
    "STORAGE_SECRET_KEY to'liq kiritilishi kerak.",
    "environment": "ENVIRONMENT faqat «production», «development» yoki «test» bo'lishi mumkin.",
}


def preflight() -> int:
    """Validate the configuration; print what is wrong in plain words instead of a traceback."""
    try:
        Settings()
    except ValidationError as exc:
        print("❌ Sozlamalarda xato — server ishga tushmadi:", file=sys.stderr)
        for error in exc.errors():
            field = str(error["loc"][0]) if error.get("loc") else ""
            reasons = str(error.get("msg", "")).removeprefix("Value error, ").split("; ")
            for reason in reasons:
                # Whole-model checks name the variable in their message.
                name = field or next((key for key in _HINTS if key.upper() in reason), "")
                if "STORAGE_*" in reason:
                    name = "storage_variables"
                hint = _HINTS.get(name, f"{name.upper() or 'Sozlama'} qiymatini tekshiring.")
                print(f"   • {hint}  ({reason})", file=sys.stderr)
        return 1
    print("Configuration OK")
    return 0


_ICONS = {"ok": "OK  ", "info": "INFO", "warning": "WARN", "error": "FAIL"}


async def _check() -> int:
    from app.bot.setup import close_bot_runtime
    from app.services.system_status import collect

    try:
        async with get_session_factory()() as session:
            result = await collect(session)
    finally:
        await close_bot_runtime()
        await dispose_engine()
    for check in result["checks"]:
        print(f"[{_ICONS[check['status']]}] {check['title']}: {check['detail']}")
    print(f"\nSummary: {result['summary']}")
    return 1 if result["summary"] == "error" else 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Kitobxon Hub maintenance commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="Synchronise permissions, roles, default settings and templates")
    sub.add_parser("check", help="Production readiness checks (database, bot, storage, worker, owners)")
    sub.add_parser("preflight", help="Validate the configuration (exit code 1 with a plain explanation)")
    args = parser.parse_args()
    if args.command == "preflight":
        sys.exit(preflight())

    settings = get_settings()
    configure_logging(settings.log_level, json_output=False)
    if args.command == "bootstrap":
        asyncio.run(_bootstrap())
    elif args.command == "check":
        sys.exit(asyncio.run(_check()))


if __name__ == "__main__":
    main()
