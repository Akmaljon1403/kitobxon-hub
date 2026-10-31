"""Optional Google Drive copy of database backups.

A second, off-site copy of each backup, on top of the primary file storage (S3/R2/local).
It talks to Google's REST API directly with a service-account JWT — no heavy Google SDK — so
the only dependencies are ``httpx`` and ``PyJWT`` (already used elsewhere).

The configuration (enabled flag, target folder id, service-account JSON) is set by a super admin
from the Admin Panel and stored in ``system_settings`` under ``backup.gdrive``; the service-account
JSON is a secret and is kept **encrypted at rest** (AES-256-GCM via SECRET_KEY) and never returned
to the browser. If nothing is set in the panel, the BACKUP_GDRIVE_* environment variables are used
as a fallback. It is OFF unless enabled with both a folder id and a valid service account.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
from dataclasses import dataclass

import httpx
import jwt
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import SystemSetting
from app.security.crypto import decrypt_secret, encrypt_secret
from app.services.audit import record_audit

logger = logging.getLogger(__name__)

# Full Drive scope: the narrower drive.file scope only reaches files the app itself created, so it
# gets "File not found" (404) when writing into a folder the owner shared with the service account
# through the Drive UI — which is exactly how this feature is set up. A dedicated service account only
# ever sees folders explicitly shared with it, so this scope stays limited to the backup folder.
_SCOPE = "https://www.googleapis.com/auth/drive"
_OAUTH_URL = "https://oauth2.googleapis.com/token"
_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
_FILES_URL = "https://www.googleapis.com/drive/v3/files"
_SETTING_KEY = "backup.gdrive"  # a private key: NOT in the public settings registry
_ENC_PURPOSE = "backup-gdrive"
# A Drive folder id is a short url-safe token; the owner may paste the whole folder link instead.
_FOLDER_URL_RE = re.compile(r"/folders/([A-Za-z0-9_-]+)")
_FOLDER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,255}$")


def _normalize_folder_id(raw: str) -> str:
    """Accept either a bare folder id or a pasted Drive link and return the id."""
    value = (raw or "").strip()
    match = _FOLDER_URL_RE.search(value)
    if match:
        return match.group(1)
    # Drop any trailing query/fragment if they pasted ".../<id>?usp=sharing" without "/folders/".
    return value.split("?", 1)[0].split("#", 1)[0].strip().strip("/")


@dataclass(frozen=True)
class GdriveConfig:
    enabled: bool
    folder_id: str
    creds: dict


def _valid_creds(data: object) -> bool:
    return isinstance(data, dict) and bool(data.get("client_email")) and bool(data.get("private_key"))


async def _stored(session: AsyncSession) -> dict | None:
    value = await session.scalar(select(SystemSetting.value).where(SystemSetting.key == _SETTING_KEY))
    return value if isinstance(value, dict) else None


def _env_config() -> GdriveConfig | None:
    """Fallback configuration from the BACKUP_GDRIVE_* environment variables."""
    settings = get_settings()
    folder = (settings.backup_gdrive_folder_id or "").strip()
    raw = settings.backup_gdrive_service_account
    if not folder or not raw:
        return None
    try:
        creds = json.loads(raw.get_secret_value())
    except (ValueError, TypeError):
        return None
    if not _valid_creds(creds):
        return None
    return GdriveConfig(enabled=bool(settings.backup_gdrive_enabled), folder_id=folder, creds=creds)


async def load_config(session: AsyncSession) -> GdriveConfig | None:
    """The usable Drive configuration (panel first, then env), or None when not configured.

    The returned config may be ``enabled=False``: the upload path checks that, the delete path does
    not (so a copy can still be cleaned up after Drive is turned off).
    """
    row = await _stored(session)
    if row is not None:
        enc = row.get("service_account_enc")
        folder = (row.get("folder_id") or "").strip()
        if not enc or not folder:
            return None
        try:
            creds = json.loads(decrypt_secret(_ENC_PURPOSE, enc))
        except Exception:
            logger.warning("Stored Google Drive credentials could not be decrypted")
            return None
        if not _valid_creds(creds):
            return None
        return GdriveConfig(enabled=bool(row.get("enabled")), folder_id=folder, creds=creds)
    return _env_config()


async def status(session: AsyncSession) -> dict:
    """What the Admin Panel shows — never the secret itself."""
    row = await _stored(session)
    if row is not None:
        folder = (row.get("folder_id") or "").strip()
        return {
            "configured": bool(row.get("service_account_enc")) and bool(folder),
            "enabled": bool(row.get("enabled")),
            "folder_id": folder or None,
            "source": "panel",
        }
    env = _env_config()
    if env is not None:
        return {"configured": True, "enabled": env.enabled, "folder_id": env.folder_id, "source": "env"}
    return {"configured": False, "enabled": False, "folder_id": None, "source": None}


async def save_config(
    session: AsyncSession, *, actor_id, enabled: bool, folder_id: str, service_account: str | None
) -> None:
    """Store the Drive config from the panel. ``service_account`` None/empty keeps the existing key."""
    from app.core.errors import ValidationFailedError

    folder = _normalize_folder_id(folder_id)
    if folder and not _FOLDER_ID_RE.match(folder):
        # Most often the owner pasted the JSON text or something else into the folder-id box.
        raise ValidationFailedError(
            "GDRIVE_BAD_FOLDER",
            "Papka ID noto'g'ri. Papka havolasidagi «/folders/» dan keyingi qisqa kodni kiriting "
            "(masalan: 1A2b3C4d5E…), yoki papka havolasini to'liq joylashtiring.",
        )
    existing = await _stored(session)
    enc = existing.get("service_account_enc") if existing else None
    provided = (service_account or "").strip()
    if provided:
        try:
            data = json.loads(provided)
        except (ValueError, TypeError) as exc:
            raise ValidationFailedError(
                "GDRIVE_BAD_JSON", "Service account fayli noto'g'ri — faylning to'liq matnini joylashtiring."
            ) from exc
        if not _valid_creds(data):
            raise ValidationFailedError(
                "GDRIVE_BAD_JSON", "Service account faylida client_email yoki private_key topilmadi."
            )
        enc = encrypt_secret(_ENC_PURPOSE, provided)
    if enabled and (not folder or not enc):
        raise ValidationFailedError(
            "GDRIVE_INCOMPLETE", "Yoqishdan oldin papka ID va service account faylini kiriting."
        )
    value = {"enabled": bool(enabled), "folder_id": folder, "service_account_enc": enc}
    statement = pg_insert(SystemSetting).values(
        key=_SETTING_KEY, value=value, description="Google Drive backup configuration", updated_by=actor_id
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[SystemSetting.key], set_={"value": value, "updated_by": actor_id}
        )
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="GDRIVE_CONFIG",
        entity_type="setting",
        entity_id=_SETTING_KEY,
        after={"enabled": value["enabled"], "folder_set": bool(folder), "key_set": bool(enc)},
    )
    await session.commit()


async def clear_config(session: AsyncSession, *, actor_id) -> None:
    await session.execute(sa_delete(SystemSetting).where(SystemSetting.key == _SETTING_KEY))
    record_audit(
        session,
        actor_id=actor_id,
        action="GDRIVE_CONFIG",
        entity_type="setting",
        entity_id=_SETTING_KEY,
        after={"cleared": True},
    )
    await session.commit()


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


async def test_config(config: GdriveConfig) -> None:
    """Raise if the credentials fail OR the target folder is not reachable (the «Test» button).

    Checking the folder itself — not just that a token can be obtained — is what catches the common
    case where the Drive folder was never shared with the service account, or the wrong id was given.
    """
    token = await _access_token(config.creds)
    async with _client(30) as client:
        resp = await client.get(
            f"{_FILES_URL}/{config.folder_id}",
            params={"fields": "id", "supportsAllDrives": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()


async def upload_backup(
    config: GdriveConfig, filename: str, data: bytes, content_type: str = "application/octet-stream"
) -> str:
    """Upload one backup blob into the configured Drive folder; return the Drive file id."""
    token = await _access_token(config.creds)
    metadata = {"name": filename, "parents": [config.folder_id]}
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


async def delete_backup_file(config: GdriveConfig, file_id: str) -> None:
    token = await _access_token(config.creds)
    async with _client(30) as client:
        resp = await client.delete(
            f"{_FILES_URL}/{file_id}",
            params={"supportsAllDrives": "true"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code not in (200, 204, 404):  # 404: already gone — fine
            resp.raise_for_status()
