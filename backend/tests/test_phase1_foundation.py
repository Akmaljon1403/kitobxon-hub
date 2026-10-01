"""Phase 1: application skeleton, health checks, error format, logging and configuration."""

from __future__ import annotations

import logging

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from app.core.config import Settings, normalize_database_url
from app.core.errors import ConflictError
from app.core.logging import JsonFormatter, RedactingFilter, redact


async def test_health_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"


async def test_health_db_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "database"}


async def test_health_redis_not_configured(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/redis")
    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"


async def test_request_id_is_generated_and_echoed(client: httpx.AsyncClient) -> None:
    generated = await client.get("/health")
    assert len(generated.headers["X-Request-ID"]) >= 8

    echoed = await client.get("/health", headers={"X-Request-ID": "client-supplied-id-123"})
    assert echoed.headers["X-Request-ID"] == "client-supplied-id-123"

    rejected = await client.get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert rejected.headers["X-Request-ID"] != "bad id with spaces"


async def test_security_headers_present(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"


async def test_unknown_route_uses_error_format(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_public_meta(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/meta")
    assert response.status_code == 200
    assert response.json()["bot_username"] == "kitobxon_test_bot"


async def test_openapi_schema_available(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/openapi.json")
    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


class Payload(BaseModel):
    phone: str
    course: int


@pytest.fixture
def error_app() -> FastAPI:
    """A tiny app with deliberately failing routes, wired exactly like the real one."""
    from app.core.errors import register_error_handlers
    from app.core.middleware import RequestContextMiddleware

    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database password=hunter2 leaked in stack trace")

    @test_app.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("ALREADY_CHECKED_IN", "Siz bu tadbirda allaqachon qayd etilgansiz.")

    @test_app.post("/validate")
    async def validate(payload: Payload) -> Payload:
        return payload

    return test_app


async def _call(app: FastAPI, method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        return await http_client.request(method, url, **kwargs)


async def test_unhandled_error_hides_internals(error_app: FastAPI, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        response = await _call(error_app, "GET", "/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_app_error_format(error_app: FastAPI) -> None:
    response = await _call(error_app, "GET", "/conflict")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_CHECKED_IN"
    assert response.json()["success"] is False


async def test_validation_error_does_not_echo_input(error_app: FastAPI) -> None:
    response = await _call(error_app, "POST", "/validate", json={"phone": "+998901234567", "course": "abc"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "course"
    assert "+998901234567" not in response.text
    assert "abc" not in response.text


def test_redaction_of_secrets() -> None:
    url = "https://api.telegram.org/bot123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/sendMessage"
    assert "AAHdqTcv" not in redact(url)
    assert "secret-value" not in redact("Authorization: Bearer secret-value")
    assert "abc123" not in redact("query_id=1&user=%7B%7D&hash=abc123")
    assert "s3cr3t" not in redact("password=s3cr3t")


def test_json_log_line_is_redacted() -> None:
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "token=%s", ("123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",), None
    )
    RedactingFilter().filter(record)
    line = JsonFormatter().format(record)
    assert "AAHdqTcv" not in line
    assert '"level": "INFO"' in line


@pytest.mark.parametrize(
    ("raw", "expected_url", "expected_args"),
    [
        (
            "postgres://u:p@db.example.com/kitob?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@db.example.com/kitob",
            {"ssl": "require"},
        ),
        ("postgresql://u:p@localhost:5432/kitob", "postgresql+asyncpg://u:p@localhost:5432/kitob", {}),
        ("postgresql+asyncpg://u:p@h/k?sslmode=disable", "postgresql+asyncpg://u:p@h/k", {}),
    ],
)
def test_database_url_normalization(raw: str, expected_url: str, expected_args: dict) -> None:
    assert normalize_database_url(raw) == (expected_url, expected_args)


def test_database_url_must_be_postgres() -> None:
    with pytest.raises(ValueError):
        normalize_database_url("mysql://u:p@h/db")


def test_settings_parse_comma_separated_lists() -> None:
    settings = Settings(
        _env_file=None,
        super_admin_telegram_ids="111, 222",
        cors_origins="https://a.example.com/, https://b.example.com",
    )
    assert settings.super_admin_telegram_ids == [111, 222]
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]
    assert Settings(_env_file=None, super_admin_telegram_ids="333").super_admin_telegram_ids == [333]


def test_production_rejects_weak_secret() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(_env_file=None, environment="production", secret_key="short")
    ok = Settings(_env_file=None, environment="production", secret_key="x" * 40)
    assert ok.is_production
