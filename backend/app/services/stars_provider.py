"""Automatic Telegram Stars delivery through the club's Stars provider (optional).

Telegram itself gives a bot no way to buy or gift Stars, so the club can plug in a third-party
provider that does. When ``STARS_API_BASE_URL`` and ``STARS_API_KEY`` are set, a confirmed Stars
order is delivered automatically — the provider sends the Stars to the member's ``@username``.
Without them, or on any error, the order falls back to the manual flow (an admin gifts the Stars
on Fragment and presses «✅ Yuborildi»), so a member is never left without their Stars.

The API key lives only in the environment (never in the database or the Admin Panel). The call is
idempotent: the same ``Idempotency-Key`` is never charged twice, so a retried delivery is safe.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20.0


class StarsProviderError(Exception):
    """The provider could not be reached or refused the order."""

    def __init__(self, message: str, *, status: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


def configured() -> bool:
    """True when both the provider address and key are set."""
    settings = get_settings()
    return bool(settings.stars_api_base_url and settings.stars_api_key)


def _client() -> httpx.AsyncClient:
    settings = get_settings()
    key = settings.stars_api_key.get_secret_value() if settings.stars_api_key else ""
    return httpx.AsyncClient(
        base_url=(settings.stars_api_base_url or "").rstrip("/"),
        headers={"X-API-Key": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _handle(username: str) -> str:
    return username if username.startswith("@") else f"@{username}"


async def send_stars(username: str, amount: int, *, idempotency_key: str) -> dict[str, Any]:
    """Ask the provider to send ``amount`` Stars to ``@username``. Raises StarsProviderError on failure.

    ``idempotency_key`` must be stable for one order (e.g. ``stars:<payment id>``) so a retry never
    charges twice."""
    async with _client() as client:
        try:
            response = await client.post(
                "/v1/stars/buy",
                headers={"Idempotency-Key": idempotency_key},
                json={"username": _handle(username), "amount": amount},
            )
        except httpx.HTTPError as exc:
            raise StarsProviderError(f"provayderga ulanib bo'lmadi: {exc}") from exc
        if response.status_code >= 400:
            payload = _safe_json(response)
            raise StarsProviderError(
                f"provayder rad etdi (HTTP {response.status_code})", status=response.status_code, payload=payload
            )
        return _safe_json(response) or {}


async def balance() -> dict[str, Any]:
    """The provider account's current balance (for the Admin Panel). Raises StarsProviderError on failure."""
    async with _client() as client:
        try:
            response = await client.get("/v1/balance")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StarsProviderError(f"provayderga ulanib bo'lmadi: {exc}") from exc
        return _safe_json(response) or {}
