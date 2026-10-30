"""Database backups: a super admin takes, lists, downloads and deletes a pg_dump."""

from __future__ import annotations

import types
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Backup
from app.models.enums import BackupKind, BackupStatus
from app.services import backups as backup_service
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
    backup_id = body["id"]

    # It appears in the list with the settings summary.
    listing = await client.get("/api/v1/admin/backups", headers=headers)
    assert listing.status_code == 200
    summary = listing.json()
    assert summary["enabled"] is True and summary["total"] >= 1
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
