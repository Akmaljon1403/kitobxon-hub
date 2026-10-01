"""Maintenance commands.

python -m app.cli bootstrap    # (re)create permissions, system roles and default settings
"""

from __future__ import annotations

import argparse
import asyncio

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


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Kitobxon Hub maintenance commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="Synchronise permissions, roles, default settings and templates")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level, json_output=False)
    if args.command == "bootstrap":
        asyncio.run(_bootstrap())


if __name__ == "__main__":
    main()
