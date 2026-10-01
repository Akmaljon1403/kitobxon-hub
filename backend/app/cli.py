"""Maintenance commands.

python -m app.cli bootstrap    # (re)create permissions, system roles and default settings
python -m app.cli check        # production readiness checks (exit code 1 on errors)
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.config import get_settings
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
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level, json_output=False)
    if args.command == "bootstrap":
        asyncio.run(_bootstrap())
    elif args.command == "check":
        sys.exit(asyncio.run(_check()))


if __name__ == "__main__":
    main()
