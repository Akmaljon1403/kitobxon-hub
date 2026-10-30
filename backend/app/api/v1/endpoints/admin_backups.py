"""Admin Panel: database backups (super admin only — «Zaxira nusxa va tiklash»)."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, SuperAdminDep
from app.core.config import get_settings
from app.models import User
from app.models.enums import BackupKind, BackupStatus
from app.schemas.backup import BackupOut, BackupSummaryOut
from app.services import backups as backup_service

router = APIRouter(prefix="/admin/backups", tags=["admin: backups"])


async def _names(db: DbSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await db.execute(select(User.id, User.first_name, User.last_name).where(User.id.in_(ids)))
    return {uid: f"{first} {last}".strip() for uid, first, last in rows}


def _out(backup, names: dict[uuid.UUID, str]) -> BackupOut:
    return BackupOut(
        id=backup.id,
        kind=backup.kind,
        status=backup.status,
        size_bytes=backup.size_bytes,
        sha256=backup.sha256,
        encrypted=backup.encrypted,
        db_name=backup.db_name,
        error=backup.error,
        created_at=backup.created_at,
        created_by_name=names.get(backup.created_by) if backup.created_by else None,
    )


@router.get("", response_model=BackupSummaryOut, summary="Backups and their settings")
async def list_backups(_: SuperAdminDep, db: DbSession) -> BackupSummaryOut:
    settings = get_settings()
    rows = await backup_service.list_backups(db, limit=100)
    names = await _names(db, {b.created_by for b in rows if b.created_by})
    last_success = next((b.created_at for b in rows if b.status == BackupStatus.SUCCESS), None)
    return BackupSummaryOut(
        enabled=settings.backups_enabled,
        encryption_enabled=settings.backup_encryption_key is not None,
        retention_daily=settings.backup_retention_daily,
        retention_monthly=settings.backup_retention_monthly,
        last_success_at=last_success,
        total=len(rows),
        backups=[_out(b, names) for b in rows],
    )


@router.post("", response_model=BackupOut, status_code=status.HTTP_201_CREATED, summary="Take a backup now")
async def create_backup(current: SuperAdminDep, db: DbSession) -> BackupOut:
    backup = await backup_service.create_backup(db, kind=BackupKind.MANUAL, actor_id=current.user.id)
    names = await _names(db, {backup.created_by} if backup.created_by else set())
    return _out(backup, names)


@router.get("/{backup_id}/download", summary="Download a backup dump file")
async def download_backup(backup_id: uuid.UUID, _: SuperAdminDep, db: DbSession) -> Response:
    filename, data = await backup_service.download(db, backup_id)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.delete("/{backup_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a backup")
async def delete_backup(backup_id: uuid.UUID, current: SuperAdminDep, db: DbSession) -> Response:
    await backup_service.delete_backup(db, actor_id=current.user.id, backup_id=backup_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
