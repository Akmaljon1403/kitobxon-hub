"""Fixed-window rate limiting.

Uses Redis when ``REDIS_URL`` is configured (limits shared by all server instances) and an
in-process store otherwise (enough for a single instance). If Redis becomes unreachable the
limiter falls back to the in-process store instead of failing requests.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Request

from app.core.errors import RateLimitedError
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimit:
    name: str
    limit: int
    window_seconds: int


class InMemoryCounter:
    def __init__(self) -> None:
        self._counts: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    async def hit(self, key: str, window_seconds: int) -> tuple[int, int]:
        """Register one hit; returns (hits in current window, seconds until the window resets)."""
        now = time.monotonic()
        async with self._lock:
            if now - self._last_cleanup > 60:
                self._counts = {k: v for k, v in self._counts.items() if v[1] > now}
                self._last_cleanup = now
            count, resets_at = self._counts.get(key, (0, now + window_seconds))
            if resets_at <= now:
                count, resets_at = 0, now + window_seconds
            count += 1
            self._counts[key] = (count, resets_at)
            return count, max(1, int(resets_at - now))

    def reset(self) -> None:
        self._counts.clear()


_memory = InMemoryCounter()


async def _hit(key: str, window_seconds: int) -> tuple[int, int]:
    redis = get_redis()
    if redis is not None:
        try:
            window = int(time.time() // window_seconds)
            redis_key = f"rl:{key}:{window}"
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, window_seconds + 1)
                count, _ = await pipe.execute()
            retry_after = window_seconds - int(time.time()) % window_seconds
            return int(count), max(1, retry_after)
        except Exception as exc:
            logger.warning("Redis rate limiter unavailable, using in-memory fallback: %s", type(exc).__name__)
    return await _memory.hit(key, window_seconds)


async def enforce(rule: RateLimit, identifier: str) -> None:
    count, retry_after = await _hit(f"{rule.name}:{identifier}", rule.window_seconds)
    if count > rule.limit:
        raise RateLimitedError(details={"retry_after": retry_after})


def client_ip(request: Request) -> str:
    # Uvicorn runs with --proxy-headers, so request.client is the real client behind the proxy.
    return request.client.host if request.client else "unknown"


def limit_by_ip(rule: RateLimit) -> Callable[[Request], Awaitable[None]]:
    """FastAPI dependency limiting a route per client IP address."""

    async def dependency(request: Request) -> None:
        await enforce(rule, client_ip(request))

    return dependency


def reset_in_memory_limits() -> None:
    """Used by tests."""
    _memory.reset()


# Rules used across the API.
# Per IP. Generous on purpose: a whole lecture hall on the campus Wi-Fi, or many phones behind
# a mobile operator's shared address, open the Mini App at the same moment. Guessing is
# useless anyway (signed launch data, one-time links); the limit only stops floods.
AUTH_LIMIT = RateLimit("auth", limit=300, window_seconds=60)
ADMIN_LOGIN_LIMIT = RateLimit("admin-login", limit=30, window_seconds=300)
# Per signed-in member, across the whole API: far above what the apps send, low enough to stop
# a stolen or scripted token from hammering expensive endpoints.
USER_API_LIMIT = RateLimit("api-user", limit=300, window_seconds=60)
