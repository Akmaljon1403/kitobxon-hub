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
from app.schemas.backup import (
    BackupOut,
    BackupSummaryOut,
    GdriveConfigIn,
    GdriveStatusOut,
    GdriveTestOut,
    RestoreIn,
    RestoreResultOut,
)
from app.services import backups as backup_service
from app.services import gdrive

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
        in_drive=backup.gdrive_file_id is not None,
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
    gdrive_status = await gdrive.status(db)
    return BackupSummaryOut(
        enabled=settings.backups_enabled,
        encryption_enabled=settings.backup_encryption_key is not None,
        gdrive_enabled=gdrive_status["enabled"],
        gdrive_configured=gdrive_status["configured"],
        gdrive_folder_id=gdrive_status["folder_id"],
        gdrive_source=gdrive_status["source"],
        restore_live_enabled=settings.allow_in_app_restore,
        retention_daily=settings.backup_retention_daily,
        retention_monthly=settings.backup_retention_monthly,
        last_success_at=last_success,
        total=len(rows),
        backups=[_out(b, names) for b in rows],
    )


# --- Google Drive backup config (super admin; declared before /{backup_id} to avoid path clashes) ---


@router.get("/gdrive", response_model=GdriveStatusOut, summary="Google Drive backup config status")
async def gdrive_config_status(_: SuperAdminDep, db: DbSession) -> GdriveStatusOut:
    return GdriveStatusOut(**await gdrive.status(db))


@router.post("/gdrive", response_model=GdriveStatusOut, summary="Save Google Drive backup config")
async def gdrive_config_save(body: GdriveConfigIn, current: SuperAdminDep, db: DbSession) -> GdriveStatusOut:
    await gdrive.save_config(
        db,
        actor_id=current.user.id,
        enabled=body.enabled,
        folder_id=body.folder_id,
        service_account=body.service_account,
    )
    return GdriveStatusOut(**await gdrive.status(db))


@router.post("/gdrive/test", response_model=GdriveTestOut, summary="Test the Google Drive connection")
async def gdrive_config_test(_: SuperAdminDep, db: DbSession) -> GdriveTestOut:
    config = await gdrive.load_config(db)
    if config is None:
        return GdriveTestOut(ok=False, message="Avval papka ID va service account faylini saqlang.")
    try:
        await gdrive.test_config(config)
    except Exception:
        return GdriveTestOut(
            ok=False,
            message=(
                "Ulanib bo'lmadi — service account yoki papka ID noto'g'ri, "
                "yoki papka service account bilan ulashilmagan."
            ),
        )
    return GdriveTestOut(ok=True, message="Ulanish muvaffaqiyatli — Google Drive tayyor.")


@router.delete("/gdrive", status_code=status.HTTP_204_NO_CONTENT, summary="Clear Google Drive backup config")
async def gdrive_config_clear(current: SuperAdminDep, db: DbSession) -> Response:
    await gdrive.clear_config(db, actor_id=current.user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.post("/{backup_id}/restore", response_model=RestoreResultOut, summary="Restore from a backup (safe)")
async def restore_backup(
    backup_id: uuid.UUID, body: RestoreIn, current: SuperAdminDep, db: DbSession
) -> RestoreResultOut:
    result = await backup_service.restore_backup(
        db, actor_id=current.user.id, backup_id=backup_id, confirm=body.confirm, live=body.live
    )
    return RestoreResultOut(**result)


@router.delete("/{backup_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a backup")
async def delete_backup(backup_id: uuid.UUID, current: SuperAdminDep, db: DbSession) -> Response:
    await backup_service.delete_backup(db, actor_id=current.user.id, backup_id=backup_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
