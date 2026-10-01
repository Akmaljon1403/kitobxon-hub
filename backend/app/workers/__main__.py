"""Run the background worker alone: ``python -m app.workers``.

Use this when the worker runs in its own container; then set WORKER_ENABLED=false for the web
containers so they only serve HTTP.
"""

from __future__ import annotations

import asyncio
import signal

from app.bot.setup import close_bot_runtime
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.logging import configure_logging
from app.workers.runner import run_worker


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await run_worker(stop)
    finally:
        await close_bot_runtime()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
