"""Phase 22: edges of the outside world — the AI service failing in every documented way,
S3-compatible storage, and the built web apps served by the backend."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest

from app.core.config import get_settings
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.core.security_headers import ADMIN_CSP, MINIAPP_CSP
from app.services import report_ai
from app.services.storage import S3Storage

# ---------------------------------------------------------------------------- AI drafting

_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _report() -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        title="Hisobot",
        objective="Kitobxonlikni rivojlantirish",
        activity_description=None,
        results=None,
        conclusion=None,
        recommendations=None,
        facts_snapshot={"attendance": {"verified": 12}},
    )


def _fake_client(monkeypatch: pytest.MonkeyPatch, outcome: Any) -> None:
    async def create(**_: Any) -> Any:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(report_ai, "is_configured", lambda: True)
    monkeypatch.setattr(
        report_ai, "_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    )


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    return cls("error", response=httpx.Response(status, request=_REQUEST), body=None)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (_status_error(anthropic.AuthenticationError, 401), "AI_AUTH_FAILED"),
        (_status_error(anthropic.RateLimitError, 429), "AI_BUSY"),
        (_status_error(anthropic.InternalServerError, 500), "AI_UNAVAILABLE"),
        (anthropic.APIConnectionError(request=_REQUEST), "AI_UNAVAILABLE"),
    ],
)
async def test_ai_failures_become_clear_messages(monkeypatch: pytest.MonkeyPatch, error: Exception, code: str) -> None:
    _fake_client(monkeypatch, error)
    with pytest.raises(ServiceUnavailableError) as raised:
        await report_ai.draft_report(_report())
    assert raised.value.code == code
    assert "api.anthropic.com" not in raised.value.message


def _response(stop_reason: str, *texts: str) -> Any:
    return SimpleNamespace(
        stop_reason=stop_reason,
        model="claude-opus-5-5",
        content=[SimpleNamespace(type="text", text=text) for text in texts],
    )


async def test_ai_refusal_and_empty_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_client(monkeypatch, _response("refusal"))
    with pytest.raises(ServiceUnavailableError) as refused:
        await report_ai.draft_report(_report())
    assert refused.value.code == "AI_REFUSED"

    _fake_client(monkeypatch, _response("end_turn", "   "))
    with pytest.raises(ServiceUnavailableError) as empty:
        await report_ai.draft_report(_report())
    assert empty.value.code == "AI_EMPTY"

    _fake_client(monkeypatch, _response("max_tokens", "Birinchi qism", "Ikkinchi qism"))
    draft = await report_ai.draft_report(_report())
    assert draft.text == "Birinchi qism\nIkkinchi qism"


async def test_ai_not_configured() -> None:
    assert get_settings().ai_api_key is None
    with pytest.raises(ServiceUnavailableError) as raised:
        await report_ai.draft_report(_report())
    assert raised.value.code == "AI_NOT_CONFIGURED"


def test_prompt_contains_only_facts_and_admin_notes() -> None:
    prompt = report_ai.build_prompt(_report())
    assert '"verified": 12' in prompt
    assert "Kitobxonlikni rivojlantirish" in prompt
    assert "takliflar" not in prompt  # empty fields are left out


# ---------------------------------------------------------------------------- S3 storage


class _FakeS3:
    class exceptions:  # mirrors boto3's client.exceptions namespace
        class NoSuchKey(Exception):
            pass

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self.objects[f"{Bucket}/{Key}"] = (Body, ContentType)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if f"{Bucket}/{Key}" not in self.objects:
            raise self.exceptions.NoSuchKey
        return {"Body": io.BytesIO(self.objects[f"{Bucket}/{Key}"][0])}

    def head_object(self, *, Bucket: str, Key: str) -> None:
        if f"{Bucket}/{Key}" not in self.objects:
            raise RuntimeError("404")

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop(f"{Bucket}/{Key}", None)


async def test_s3_storage_round_trip() -> None:
    storage = S3Storage(
        endpoint="https://example.r2.cloudflarestorage.com",
        region="auto",
        access_key="key",
        secret_key="secret",  # fake credentials: no network call is made
        bucket="kitobxon",
    )
    storage.client = _FakeS3()
    await storage.put("reports/1/report.pdf", b"%PDF-1.7", "application/pdf")
    assert storage.client.objects["kitobxon/reports/1/report.pdf"] == (b"%PDF-1.7", "application/pdf")
    assert await storage.exists("reports/1/report.pdf") is True
    assert await storage.get("reports/1/report.pdf") == b"%PDF-1.7"
    await storage.delete("reports/1/report.pdf")
    assert await storage.exists("reports/1/report.pdf") is False
    with pytest.raises(NotFoundError):
        await storage.get("reports/1/report.pdf")


# ---------------------------------------------------------------------------- web apps


async def test_backend_serves_both_web_apps_with_their_policies(tmp_path: Path) -> None:
    from app.main import create_app

    for folder in ("miniapp", "admin"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "index.html").write_text(f"<!doctype html><title>{folder}</title>", encoding="utf-8")
    app = create_app(get_settings().model_copy(update={"static_dir": str(tmp_path)}))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        miniapp = await client.get("/app/")
        admin = await client.get("/admin/")
    assert miniapp.status_code == 200 and "<title>miniapp</title>" in miniapp.text
    assert miniapp.headers["Content-Security-Policy"] == MINIAPP_CSP
    assert admin.status_code == 200 and "<title>admin</title>" in admin.text
    assert admin.headers["Content-Security-Policy"] == ADMIN_CSP
    assert "frame-ancestors https://web.telegram.org" in admin.headers["Content-Security-Policy"]
