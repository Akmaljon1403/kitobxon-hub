"""The worker loop: scheduled checks every ``WORKER_INTERVAL_SECONDS`` and the notification
sender whenever something is due. Runs inside the web process by default (cheapest setup) or
alone with ``python -m app.workers``."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

from app.bot.setup import get_bot_runtime
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.services.notifications import wait_for_work
from app.workers.channel_sender import send_channel_posts
from app.workers.jobs import run_scheduled_jobs
from app.workers.sender import send_due_notifications

logger = logging.getLogger(__name__)
BATCH = 100


async def run_worker(stop: asyncio.Event) -> None:
    interval = get_settings().worker_interval_seconds
    factory = get_session_factory()
    last_jobs = 0.0
    logger.info("Background worker started (checks every %s s)", interval)
    while not stop.is_set():
        try:
            if time.monotonic() - last_jobs >= interval:
                last_jobs = time.monotonic()
                await run_scheduled_jobs(factory)
            runtime = get_bot_runtime()
            if runtime is not None:
                while not stop.is_set():
                    report = await send_due_notifications(factory, runtime.bot, limit=BATCH)
                    if report.total < BATCH:
                        break
                await send_channel_posts(factory, runtime.bot)
        except Exception:
            logger.exception("Background worker iteration failed")
        if await _sleep_or_wake(stop, interval):
            # Woken by a request that queued messages: give its transaction a moment to commit.
            await asyncio.sleep(1)
    logger.info("Background worker stopped")


async def _sleep_or_wake(stop: asyncio.Event, interval: float) -> bool:
    """Wait until the next check, a wake-up from this process, or shutdown. True if woken early."""
    stop_task = asyncio.create_task(stop.wait())
    wake_task = asyncio.create_task(wait_for_work(interval))
    done, pending = await asyncio.wait({stop_task, wake_task}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    return wake_task in done and wake_task.result() and not stop.is_set()


class WorkerHandle:
    """Start/stop helper used by the web app's lifespan."""

    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(run_worker(self._stop), name="kitobxon-worker")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
