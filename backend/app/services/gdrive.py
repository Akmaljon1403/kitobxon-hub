"""Optional Google Drive copy of database backups.

A second, off-site copy of each backup, on top of the primary file storage (S3/R2/local).
It talks to Google's REST API directly with a service-account JWT — no heavy Google SDK — so
the only dependencies are ``httpx`` and ``PyJWT`` (already used elsewhere).

It is OFF unless ``backup_gdrive_enabled`` is true and both the service-account JSON and the target
folder id are set. The service-account JSON is a secret and is never written to code, logs or reports;
the owner shares the Drive folder with the service account's e-mail so it may upload into it.
"""

from __future__ import annotations

import json
import logging
import secrets
import time

import httpx
import jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SCOPE = "https://www.googleapis.com/auth/drive.file"
_OAUTH_URL = "https://oauth2.googleapis.com/token"
_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
_FILES_URL = "https://www.googleapis.com/drive/v3/files"


def _creds() -> dict | None:
    """Parse the service-account JSON from settings, or None when it is unset/invalid."""
    raw = get_settings().backup_gdrive_service_account
    if not raw:
        return None
    try:
        data = json.loads(raw.get_secret_value())
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) and data.get("client_email") and data.get("private_key") else None


def enabled() -> bool:
    settings = get_settings()
    return bool(settings.backup_gdrive_enabled and settings.backup_gdrive_folder_id and _creds())


def _client(timeout: float) -> httpx.AsyncClient:
    """The HTTP client (its own function so tests can swap in a mock transport)."""
    return httpx.AsyncClient(timeout=timeout)


def _build_signed_jwt(creds: dict, *, now: int | None = None) -> str:
    """A short-lived RS256 assertion, signed with the service-account private key."""
    issued = now if now is not None else int(time.time())
    claims = {
        "iss": creds["client_email"],
        "scope": _SCOPE,
        "aud": _OAUTH_URL,
        "iat": issued,
        "exp": issued + 3600,
    }
    return jwt.encode(claims, creds["private_key"], algorithm="RS256")


async def _access_token(creds: dict) -> str:
    assertion = _build_signed_jwt(creds)
    async with _client(30) as client:
        resp = await client.post(
            _OAUTH_URL,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def upload_backup(filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload one backup blob into the configured Drive folder; return the Drive file id."""
    creds = _creds()
    if creds is None:  # pragma: no cover - guarded by enabled() at the call site
        raise RuntimeError("Google Drive is not configured")
    folder_id = get_settings().backup_gdrive_folder_id
    token = await _access_token(creds)
    metadata = {"name": filename, "parents": [folder_id]}
    # Google Drive wants a multipart/related body (metadata part, then the file part).
    boundary = f"kitobxon-{secrets.token_hex(16)}"
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + json.dumps(metadata).encode()
        + f"\r\n--{boundary}\r\nContent-Type: {content_type}\r\n\r\n".encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": f"multipart/related; boundary={boundary}"}
    async with _client(300) as client:
        resp = await client.post(
            _UPLOAD_URL,
            params={"uploadType": "multipart", "supportsAllDrives": "true"},
            headers=headers,
            content=body,
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def delete_backup_file(file_id: str) -> None:
    creds = _creds()
    if creds is None:  # pragma: no cover - guarded by enabled() at the call site
        raise RuntimeError("Google Drive is not configured")
    token = await _access_token(creds)
    async with _client(30) as client:
        resp = await client.delete(
            f"{_FILES_URL}/{file_id}",
            params={"supportsAllDrives": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code not in (200, 204, 404):  # 404: already gone — fine
            resp.raise_for_status()
