"""Unit tests for the Stars provider client (no real network — an httpx MockTransport stands in)."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from app.services import stars_provider


class _FakeSettings:
    def __init__(self, base: str | None, key: str | None) -> None:
        self.stars_api_base_url = base
        self.stars_api_key = SecretStr(key) if key else None


def test_configured_needs_both(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stars_provider, "get_settings", lambda: _FakeSettings(None, None))
    assert stars_provider.configured() is False
    monkeypatch.setattr(stars_provider, "get_settings", lambda: _FakeSettings("https://p.test", None))
    assert stars_provider.configured() is False
    monkeypatch.setattr(stars_provider, "get_settings", lambda: _FakeSettings("https://p.test", "xst_live_abc"))
    assert stars_provider.configured() is True


async def test_client_carries_base_url_and_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stars_provider, "get_settings", lambda: _FakeSettings("https://p.test/", "xst_live_abc"))
    client = stars_provider._client()
    try:
        assert str(client.base_url) == "https://p.test"
        assert client.headers["x-api-key"] == "xst_live_abc"
        assert client.headers["authorization"] == "Bearer xst_live_abc"
    finally:
        await client.aclose()


async def test_send_stars_posts_and_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["idempotency"] = request.headers.get("idempotency-key")
        return httpx.Response(200, json={"request_id": "r1", "status": "queued"})

    client = httpx.AsyncClient(base_url="https://p.test", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(stars_provider, "_client", lambda: client)
    result = await stars_provider.send_stars("durov", 50, idempotency_key="stars:1")
    assert result == {"request_id": "r1", "status": "queued"}
    assert seen["url"].endswith("/v1/stars/buy")
    assert seen["body"] == {"username": "@durov", "amount": 50}  # the «@» is added for a bare username
    assert seen["idempotency"] == "stars:1"


async def test_send_stars_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = httpx.AsyncClient(
        base_url="https://p.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(402, json={"error": "insufficient"})),
    )
    monkeypatch.setattr(stars_provider, "_client", lambda: client)
    with pytest.raises(stars_provider.StarsProviderError) as excinfo:
        await stars_provider.send_stars("@durov", 50, idempotency_key="stars:2")
    assert excinfo.value.status == 402


async def test_balance_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    client = httpx.AsyncClient(
        base_url="https://p.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"balance": 1234})),
    )
    monkeypatch.setattr(stars_provider, "_client", lambda: client)
    assert (await stars_provider.balance())["balance"] == 1234


def _raise(_: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("unreachable")


async def test_connection_errors_become_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    # A fresh client per call: send_stars/balance each close the client they open.
    monkeypatch.setattr(
        stars_provider,
        "_client",
        lambda: httpx.AsyncClient(base_url="https://p.test", transport=httpx.MockTransport(_raise)),
    )
    with pytest.raises(stars_provider.StarsProviderError):
        await stars_provider.send_stars("durov", 10, idempotency_key="k")
    with pytest.raises(stars_provider.StarsProviderError):
        await stars_provider.balance()


async def test_non_json_response_is_tolerated(monkeypatch: pytest.MonkeyPatch) -> None:
    client = httpx.AsyncClient(
        base_url="https://p.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"OK")),
    )
    monkeypatch.setattr(stars_provider, "_client", lambda: client)
    assert await stars_provider.send_stars("durov", 10, idempotency_key="k") == {}
