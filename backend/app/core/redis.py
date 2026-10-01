"""Optional Redis connection.

Redis is not required to run Kitobxon Hub. When ``REDIS_URL`` is not configured the
application falls back to in-process alternatives (for example the in-memory rate
limiter), which is fine for a single server instance.
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis | None:
    global _client
    settings = get_settings()
    if not settings.redis_url:
        return None
    if _client is None:
        _client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            health_check_interval=30,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None
