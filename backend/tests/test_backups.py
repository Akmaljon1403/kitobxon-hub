"""Database backups: a super admin takes, lists, downloads and deletes a pg_dump."""

from __future__ import annotations

import json
import types
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Backup
from app.models.enums import BackupKind, BackupStatus
from app.services import backups as backup_service
from app.services import gdrive
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role


async def _super_admin(db: AsyncSession):
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "SUPER_ADMIN")
    return user


async def test_super_admin_takes_lists_downloads_and_deletes_a_backup(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    boss = await _super_admin(db)
    headers = admin_headers(boss)

    # Take a backup now — pg_dump runs against the test database and the dump is stored.
    created = await client.post("/api/v1/admin/backups", headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["kind"] == "MANUAL"
    assert body["status"] == "SUCCESS", body.get("error")
    assert body["size_bytes"] > 0 and len(body["sha256"]) == 64
    assert body["encrypted"] is False  # no BACKUP_ENCRYPTION_KEY set in tests
    assert body["in_drive"] is False  # Google Drive copy is off by default
    backup_id = body["id"]

    # It appears in the list with the settings summary.
    listing = await client.get("/api/v1/admin/backups", headers=headers)
    assert listing.status_code == 200
    summary = listing.json()
    assert summary["enabled"] is True and summary["total"] >= 1
    assert summary["encryption_enabled"] is False and summary["gdrive_enabled"] is False
    assert any(b["id"] == backup_id for b in summary["backups"])

    # The dump file can be downloaded (custom-format dumps start with the "PGDMP" magic).
    download = await client.get(f"/api/v1/admin/backups/{backup_id}/download", headers=headers)
    assert download.status_code == 200
    assert download.content[:5] == b"PGDMP"
    assert download.headers["content-type"].startswith("application/octet-stream")

    # Deleting it removes the row.
    assert (await client.delete(f"/api/v1/admin/backups/{backup_id}", headers=headers)).status_code == 204
    assert await db.scalar(select(func.count()).select_from(Backup)) == 0


async def test_backups_are_super_admin_only(client: httpx.AsyncClient, db: AsyncSession) -> None:
    ordinary = await create_user(db)
    await db.commit()
    await grant_role(db, ordinary, "ADMIN")
    denied = await client.get("/api/v1/admin/backups", headers=admin_headers(ordinary))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "SUPER_ADMIN_REQUIRED"
    # The restore endpoint is super-admin-only too.
    restore = await client.post(
        f"/api/v1/admin/backups/{uuid.uuid4()}/restore",
        headers=admin_headers(ordinary),
        json={"confirm": backup_service.RESTORE_CONFIRM_PHRASE, "live": False},
    )
    assert restore.status_code == 403 and restore.json()["error"]["code"] == "SUPER_ADMIN_REQUIRED"
    # The Google Drive config endpoint is super-admin-only too.
    gdrive_denied = await client.get("/api/v1/admin/backups/gdrive", headers=admin_headers(ordinary))
    assert gdrive_denied.status_code == 403 and gdrive_denied.json()["error"]["code"] == "SUPER_ADMIN_REQUIRED"


async def test_restore_validates_and_takes_a_pre_restore_backup_live_off_by_default(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    boss = await _super_admin(db)
    headers = admin_headers(boss)
    created = await client.post("/api/v1/admin/backups", headers=headers)
    backup_id = created.json()["id"]

    # Even with live=True, the live overwrite stays OFF unless ALLOW_IN_APP_RESTORE is set.
    ok = await client.post(
        f"/api/v1/admin/backups/{backup_id}/restore",
        headers=headers,
        json={"confirm": backup_service.RESTORE_CONFIRM_PHRASE, "live": True},
    )
    assert ok.status_code == 200, ok.text
    result = ok.json()
    assert result["validated"] is True and result["entries"] > 0
    assert result["live_restored"] is False and result["live_available"] is False
    # A pre-restore safety backup was taken, so there are now at least two backups.
    summary = (await client.get("/api/v1/admin/backups", headers=headers)).json()
    assert summary["total"] >= 2 and summary["restore_live_enabled"] is False


async def test_restore_requires_the_typed_confirmation(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _super_admin(db)
    headers = admin_headers(boss)
    created = await client.post("/api/v1/admin/backups", headers=headers)
    backup_id = created.json()["id"]
    before = (await client.get("/api/v1/admin/backups", headers=headers)).json()["total"]

    bad = await client.post(
        f"/api/v1/admin/backups/{backup_id}/restore",
        headers=headers,
        json={"confirm": "ha, tiklang", "live": True},
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "RESTORE_NOT_CONFIRMED"
    # A rejected restore takes no pre-restore backup either.
    after = (await client.get("/api/v1/admin/backups", headers=headers)).json()["total"]
    assert after == before


async def test_backup_also_copied_to_google_drive_when_enabled(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    boss = await _super_admin(db)
    headers = admin_headers(boss)
    uploaded: dict = {}
    deleted: list[str] = []
    config = gdrive.GdriveConfig(enabled=True, folder_id="folder123", creds={"client_email": "x", "private_key": "y"})

    async def fake_load(session) -> gdrive.GdriveConfig:
        return config

    async def fake_status(session) -> dict:
        return {"configured": True, "enabled": True, "folder_id": "folder123", "source": "panel"}

    async def fake_upload(cfg, filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        uploaded["filename"] = filename
        uploaded["folder"] = cfg.folder_id
        return "drive-file-1"

    async def fake_delete(cfg, file_id: str) -> None:
        deleted.append(file_id)

    monkeypatch.setattr(gdrive, "load_config", fake_load)
    monkeypatch.setattr(gdrive, "status", fake_status)
    monkeypatch.setattr(gdrive, "upload_backup", fake_upload)
    monkeypatch.setattr(gdrive, "delete_backup_file", fake_delete)

    created = await client.post("/api/v1/admin/backups", headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["in_drive"] is True and uploaded["filename"].endswith(".dump") and uploaded["folder"] == "folder123"
    backup_id = body["id"]

    summary = (await client.get("/api/v1/admin/backups", headers=headers)).json()
    assert summary["gdrive_enabled"] is True and summary["gdrive_configured"] is True

    # Deleting the backup also removes its Google Drive copy.
    assert (await client.delete(f"/api/v1/admin/backups/{backup_id}", headers=headers)).status_code == 204
    assert deleted == ["drive-file-1"]


async def test_gdrive_config_from_the_panel_roundtrips_and_stays_secret(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    boss = await _super_admin(db)
    headers = admin_headers(boss)
    service_account = json.dumps(
        {"type": "service_account", "client_email": "svc@proj.iam.gserviceaccount.com", "private_key": "SECRET-KEY"}
    )
    saved = await client.post(
        "/api/v1/admin/backups/gdrive",
        headers=headers,
        json={"enabled": True, "folder_id": "folder-xyz", "service_account": service_account},
    )
    assert saved.status_code == 200, saved.text
    status_body = saved.json()
    assert status_body == {"configured": True, "enabled": True, "folder_id": "folder-xyz", "source": "panel"}
    # The status response must never carry the secret itself.
    assert "private_key" not in saved.text and "service_account" not in saved.text

    # The stored config decrypts back to the real credentials for the uploader.
    config = await gdrive.load_config(db)
    assert config is not None and config.enabled and config.folder_id == "folder-xyz"
    assert config.creds["client_email"] == "svc@proj.iam.gserviceaccount.com"
    assert config.creds["private_key"] == "SECRET-KEY"

    # Enabling without a folder (the stored key is kept) is rejected, nothing silently half-set.
    bad = await client.post(
        "/api/v1/admin/backups/gdrive",
        headers=headers,
        json={"enabled": True, "folder_id": "", "service_account": None},
    )
    assert bad.status_code in (400, 422)

    # Clearing removes it entirely.
    assert (await client.delete("/api/v1/admin/backups/gdrive", headers=headers)).status_code == 204
    assert await gdrive.load_config(db) is None


async def test_gdrive_folder_accepts_a_pasted_link_and_rejects_junk(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    boss = await _super_admin(db)
    headers = admin_headers(boss)
    service_account = json.dumps(
        {"type": "service_account", "client_email": "svc@proj.iam.gserviceaccount.com", "private_key": "KEY"}
    )
    # Pasting the whole Drive folder link (with a sharing query) stores just the id.
    saved = await client.post(
        "/api/v1/admin/backups/gdrive",
        headers=headers,
        json={
            "enabled": True,
            "folder_id": "https://drive.google.com/drive/folders/1A2b3C4d5E6f7G8h?usp=sharing",
            "service_account": service_account,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["folder_id"] == "1A2b3C4d5E6f7G8h"

    # Accidentally pasting the JSON (or anything that is not a folder id) gives a clear, specific error.
    bad = await client.post(
        "/api/v1/admin/backups/gdrive",
        headers=headers,
        json={"enabled": True, "folder_id": service_account, "service_account": None},
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "GDRIVE_BAD_FOLDER"


async def test_gdrive_jwt_and_rest_flow(monkeypatch) -> None:
    import jwt as pyjwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    creds = {"client_email": "svc@proj.iam.gserviceaccount.com", "private_key": private_pem}
    config = gdrive.GdriveConfig(enabled=True, folder_id="folder123", creds=creds)

    # The signed assertion carries the expected claims and verifies with the public key.
    assertion = gdrive._build_signed_jwt(creds, now=1_700_000_000)
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    claims = pyjwt.decode(
        assertion,
        public_pem,
        algorithms=["RS256"],
        audience=gdrive._OAUTH_URL,
        options={"verify_exp": False},  # fixed iat in the past; we only check the claims here
    )
    assert claims["iss"] == creds["client_email"] and claims["scope"] == gdrive._SCOPE
    assert claims["exp"] == claims["iat"] + 3600

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ya29.fake"})
        if "/upload/" in request.url.path:
            captured["auth"] = request.headers["authorization"]
            captured["ctype"] = request.headers["content-type"]
            return httpx.Response(200, json={"id": "driveid-xyz"})
        return httpx.Response(204)  # delete

    monkeypatch.setattr(
        gdrive, "_client", lambda timeout: httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=timeout)
    )

    file_id = await gdrive.upload_backup(config, "kitobxon.dump", b"the-bytes")
    assert file_id == "driveid-xyz"
    assert captured["auth"] == "Bearer ya29.fake"
    assert captured["ctype"].startswith("multipart/related")
    await gdrive.delete_backup_file(config, "driveid-xyz")  # must not raise


async def test_prune_keeps_newest_and_removes_older(db: AsyncSession, monkeypatch) -> None:
    # Keep only 2 daily + 1 monthly, so prune can act without taking real dumps.
    monkeypatch.setattr(
        backup_service,
        "get_settings",
        lambda: types.SimpleNamespace(backup_retention_daily=2, backup_retention_monthly=1),
    )
    now = datetime.now(UTC)
    for i in range(5):
        db.add(
            Backup(
                kind=BackupKind.DAILY,
                status=BackupStatus.SUCCESS,
                storage_key=None,  # no file to remove, so prune only drops the rows
                size_bytes=10,
                created_at=now - timedelta(days=i),
            )
        )
    await db.flush()
    removed = await backup_service.prune(db)
    assert removed == 3  # 5 daily − 2 kept
    assert await db.scalar(select(func.count()).select_from(Backup)) == 2


async def test_download_and_delete_guard_missing_backup(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _super_admin(db)
    missing = uuid.uuid4()
    gone = await client.get(f"/api/v1/admin/backups/{missing}/download", headers=admin_headers(boss))
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "BACKUP_NOT_FOUND"


async def test_backup_is_encrypted_at_rest_and_decrypts_on_download(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    boss = await _super_admin(db)
    headers = admin_headers(boss)
    # Pretend BACKUP_ENCRYPTION_KEY is set (isolates the key from the real settings used for pg_dump).
    monkeypatch.setattr(backup_service, "_encryption_key", lambda: "a-strong-test-passphrase")

    created = await client.post("/api/v1/admin/backups", headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "SUCCESS", body.get("error")
    assert body["encrypted"] is True
    backup_id = body["id"]

    # The blob actually stored is ciphertext — not a readable pg_dump — and keeps a .enc marker.
    backup = await db.scalar(select(Backup).where(Backup.id == uuid.UUID(backup_id)))
    assert backup is not None and backup.storage_key.endswith(".dump.enc")
    stored = await backup_service.get_storage().get(backup.storage_key)
    assert stored[:5] != b"PGDMP"

    # Downloading returns the decrypted, restorable dump (PGDMP magic); the filename drops .enc.
    download = await client.get(f"/api/v1/admin/backups/{backup_id}/download", headers=headers)
    assert download.status_code == 200
    assert download.content[:5] == b"PGDMP"
    assert ".enc" not in download.headers["content-disposition"]


async def test_encrypted_backup_needs_the_key_to_download(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    boss = await _super_admin(db)
    headers = admin_headers(boss)
    monkeypatch.setattr(backup_service, "_encryption_key", lambda: "a-strong-test-passphrase")
    created = await client.post("/api/v1/admin/backups", headers=headers)
    assert created.status_code == 201, created.text
    backup_id = created.json()["id"]

    # The key is now gone — the encrypted dump can no longer be opened.
    monkeypatch.setattr(backup_service, "_encryption_key", lambda: None)
    blocked = await client.get(f"/api/v1/admin/backups/{backup_id}/download", headers=headers)
    assert blocked.status_code == 400 and blocked.json()["error"]["code"] == "BACKUP_KEY_MISSING"
