"""Database backups.

A backup is a ``pg_dump`` custom-format dump (``-Fc``: compressed and restorable with
``pg_restore``). The dump file is kept in the configured file storage — the same place as
covers and certificates — so on the cloud it lands in durable object storage (S3/R2) and on
an institute server on the persistent disk. This module never deletes or changes club data;
it only reads the database out, and prunes *old backup files* by the retention settings.

Restoring is deliberately NOT a one-click button here: replacing the live database is a
manual, supervised operation (see docs/BACKUP_RESTORE_GUIDE_UZ.md). An admin downloads the
dump and a human with server access restores it with ``pg_restore`` after taking a fresh
pre-restore backup.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Backup
from app.models.enums import BackupKind, BackupStatus
from app.services.audit import record_audit
from app.services.storage import get_storage
from app.utils.timezone import local_tz

logger = logging.getLogger(__name__)

_PGDUMP_TIMEOUT = 600  # seconds; a club database is small, but a slow network link needs room
_URL_IN_TEXT = re.compile(r"postgres(?:ql)?(?:\+\w+)?://\S+")


def _libpq_url() -> str:
    """The database URL in libpq form (no SQLAlchemy ``+driver``) for pg_dump / pg_restore."""
    return re.sub(r"^postgres(?:ql)?\+\w+://", "postgresql://", get_settings().database_url)


def _db_name() -> str:
    path = urlsplit(_libpq_url()).path.lstrip("/")
    return path or "kitobxon"


def _scrub(text: str) -> str:
    """Remove any connection string (which carries the password) before storing an error."""
    return _URL_IN_TEXT.sub("<database-url>", text).strip()[-500:]


async def _run_pg_dump(target: Path) -> None:
    settings = get_settings()
    process = await asyncio.create_subprocess_exec(
        settings.pg_dump_path,
        "--no-owner",
        "--no-privileges",
        "--format=custom",
        "--file",
        str(target),
        _libpq_url(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=_PGDUMP_TIMEOUT)
    except TimeoutError as exc:
        process.kill()
        raise RuntimeError("pg_dump timed out") from exc
    if process.returncode != 0:
        raise RuntimeError(_scrub(stderr.decode("utf-8", "replace")) or "pg_dump failed")


async def _already_taken(session: AsyncSession, kind: BackupKind, now: datetime) -> Backup | None:
    """A successful automatic backup of this kind already exists for today / this month."""
    start = now.astimezone(local_tz())
    day_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = day_start.replace(day=1) if kind == BackupKind.MONTHLY else day_start
    return await session.scalar(
        select(Backup)
        .where(
            Backup.kind == kind,
            Backup.status == BackupStatus.SUCCESS,
            Backup.created_at >= period_start.astimezone(UTC),
        )
        .limit(1)
    )


async def create_backup(
    session: AsyncSession, *, kind: BackupKind, actor_id: uuid.UUID | None = None, skip_if_exists: bool = False
) -> Backup:
    """Take one backup now. On failure a FAILED row is still recorded (the error is secret-free)."""
    now = datetime.now(UTC)
    if skip_if_exists and (existing := await _already_taken(session, kind, now)) is not None:
        return existing
    db_name = _db_name()
    stamp = now.astimezone(local_tz()).strftime("%Y%m%d-%H%M%S")
    key = f"backups/{kind.value.lower()}/kitobxon_{db_name}_{stamp}_{uuid.uuid4().hex[:8]}.dump"
    try:
        with tempfile.TemporaryDirectory(prefix="kitobxon-backup-") as tmp:
            target = Path(tmp) / "dump"
            await _run_pg_dump(target)
            data = target.read_bytes()
        await get_storage().put(key, data, "application/octet-stream")
        backup = Backup(
            kind=kind,
            status=BackupStatus.SUCCESS,
            storage_key=key,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            db_name=db_name,
            created_by=actor_id,
        )
    except Exception as exc:
        logger.exception("Backup (%s) failed", kind.value)
        backup = Backup(
            kind=kind, status=BackupStatus.FAILED, db_name=db_name, created_by=actor_id, error=_scrub(str(exc))
        )
    session.add(backup)
    await session.flush()
    if actor_id is not None:
        record_audit(
            session,
            actor_id=actor_id,
            action="BACKUP_CREATE",
            entity_type="backup",
            entity_id=backup.id,
            after={"kind": kind.value, "status": backup.status.value},
        )
    await session.commit()
    return backup


async def list_backups(session: AsyncSession, *, limit: int = 100) -> list[Backup]:
    rows = await session.scalars(select(Backup).order_by(Backup.created_at.desc()).limit(limit))
    return list(rows)


async def get_backup(session: AsyncSession, backup_id: uuid.UUID) -> Backup:
    backup = await session.get(Backup, backup_id)
    if backup is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("BACKUP_NOT_FOUND", "Zaxira nusxa topilmadi.")
    return backup


async def download(session: AsyncSession, backup_id: uuid.UUID) -> tuple[str, bytes]:
    backup = await get_backup(session, backup_id)
    if backup.status != BackupStatus.SUCCESS or not backup.storage_key:
        from app.core.errors import BadRequestError

        raise BadRequestError("BACKUP_UNAVAILABLE", "Bu zaxira nusxa fayli mavjud emas.")
    data = await get_storage().get(backup.storage_key)
    return backup.storage_key.rsplit("/", 1)[-1], data


async def delete_backup(session: AsyncSession, *, actor_id: uuid.UUID, backup_id: uuid.UUID) -> None:
    backup = await get_backup(session, backup_id)
    if backup.storage_key:
        try:
            await get_storage().delete(backup.storage_key)
        except Exception:  # an orphaned file is harmless; the row still goes
            logger.info("A backup file could not be removed from storage")
    record_audit(
        session,
        actor_id=actor_id,
        action="BACKUP_DELETE",
        entity_type="backup",
        entity_id=backup.id,
        before={"kind": backup.kind.value, "key": backup.storage_key},
    )
    await session.delete(backup)
    await session.commit()


async def prune(session: AsyncSession) -> int:
    """Keep the newest N daily and M monthly successful backups; delete older files. Manual stays."""
    settings = get_settings()
    removed = 0
    for kind, keep in (
        (BackupKind.DAILY, settings.backup_retention_daily),
        (BackupKind.MONTHLY, settings.backup_retention_monthly),
    ):
        old = list(
            await session.scalars(
                select(Backup)
                .where(Backup.kind == kind, Backup.status == BackupStatus.SUCCESS)
                .order_by(Backup.created_at.desc())
                .offset(keep)
            )
        )
        for backup in old:
            if backup.storage_key:
                try:
                    await get_storage().delete(backup.storage_key)
                except Exception:
                    logger.info("An old backup file could not be removed from storage")
            await session.delete(backup)
            removed += 1
    if removed:
        await session.commit()
    return removed


async def run_scheduled(session: AsyncSession) -> int:
    """Worker entry (fires in the 23:00 Asia/Tashkent hour): one nightly backup, a monthly one on
    the 1st, then prune. Idempotent — running again the same night takes nothing new."""
    settings = get_settings()
    if not settings.backups_enabled or datetime.now(local_tz()).hour != 23:
        return 0
    taken = 0
    daily = await create_backup(session, kind=BackupKind.DAILY, skip_if_exists=True)
    taken += 1 if daily.created_at.astimezone(local_tz()).date() == datetime.now(local_tz()).date() else 0
    if datetime.now(local_tz()).day == 1:
        await create_backup(session, kind=BackupKind.MONTHLY, skip_if_exists=True)
    await prune(session)
    return taken
