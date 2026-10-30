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
from app.services import gdrive
from app.services.audit import record_audit
from app.services.storage import get_storage
from app.utils.timezone import local_tz

logger = logging.getLogger(__name__)

_PGDUMP_TIMEOUT = 600  # seconds; a club database is small, but a slow network link needs room
_URL_IN_TEXT = re.compile(r"postgres(?:ql)?(?:\+\w+)?://\S+")

# AES-256-GCM at-rest encryption for the stored dump. The 32-byte key is derived from
# BACKUP_ENCRYPTION_KEY so the owner can set any strong passphrase; the nonce is prepended
# to the ciphertext. The dump is useless to anyone holding the storage but not this key.
_BACKUP_AAD = b"kitobxon-backup"
_BACKUP_NONCE_BYTES = 12


def _encryption_key() -> str | None:
    key = get_settings().backup_encryption_key
    value = key.get_secret_value().strip() if key else ""
    return value or None


def _derive_backup_key(passphrase: str) -> bytes:
    return hashlib.sha256(f"kitobxon-backup:{passphrase}".encode()).digest()


def _encrypt(data: bytes, passphrase: str) -> bytes:
    import secrets

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = secrets.token_bytes(_BACKUP_NONCE_BYTES)
    ciphertext = AESGCM(_derive_backup_key(passphrase)).encrypt(nonce, data, _BACKUP_AAD)
    return nonce + ciphertext


def _decrypt(blob: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce, ciphertext = blob[:_BACKUP_NONCE_BYTES], blob[_BACKUP_NONCE_BYTES:]
    return AESGCM(_derive_backup_key(passphrase)).decrypt(nonce, ciphertext, _BACKUP_AAD)


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
    passphrase = _encryption_key()
    suffix = ".dump.enc" if passphrase else ".dump"
    key = f"backups/{kind.value.lower()}/kitobxon_{db_name}_{stamp}_{uuid.uuid4().hex[:8]}{suffix}"
    try:
        with tempfile.TemporaryDirectory(prefix="kitobxon-backup-") as tmp:
            target = Path(tmp) / "dump"
            await _run_pg_dump(target)
            data = target.read_bytes()
        # sha256 is of the plaintext dump, so integrity is verified after decryption on restore.
        checksum = hashlib.sha256(data).hexdigest()
        stored = _encrypt(data, passphrase) if passphrase else data
        await get_storage().put(key, stored, "application/octet-stream")
        # Best-effort off-site copy to Google Drive (same bytes, so an encrypted dump stays encrypted).
        # A Drive failure must never fail the backup — the primary storage copy already succeeded.
        gdrive_file_id: str | None = None
        try:
            cfg = await gdrive.load_config(session)
            if cfg is not None and cfg.enabled:
                gdrive_file_id = await gdrive.upload_backup(cfg, key.rsplit("/", 1)[-1], stored)
        except Exception:
            logger.exception("Google Drive copy failed for a %s backup", kind.value)
        backup = Backup(
            kind=kind,
            status=BackupStatus.SUCCESS,
            storage_key=key,
            size_bytes=len(data),
            sha256=checksum,
            encrypted=bool(passphrase),
            gdrive_file_id=gdrive_file_id,
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
    stored = await get_storage().get(backup.storage_key)
    data = await _plaintext(backup, stored)
    # The downloaded file is always a ready-to-restore .dump (decrypted); drop the .enc marker.
    filename = backup.storage_key.rsplit("/", 1)[-1].removesuffix(".enc")
    return filename, data


async def _plaintext(backup: Backup, stored: bytes) -> bytes:
    """Return the restorable dump bytes: decrypt if the backup was encrypted and verify its checksum."""
    from app.core.errors import BadRequestError

    if backup.encrypted:
        passphrase = _encryption_key()
        if not passphrase:
            raise BadRequestError(
                "BACKUP_KEY_MISSING", "Bu zaxira nusxa shifrlangan — BACKUP_ENCRYPTION_KEY sozlanmagan."
            )
        try:
            data = _decrypt(stored, passphrase)
        except Exception as exc:  # wrong key or a corrupted file
            raise BadRequestError(
                "BACKUP_DECRYPT_FAILED", "Zaxira nusxani ochib bo'lmadi — shifrlash kaliti noto'g'ri."
            ) from exc
    else:
        data = stored
    if backup.sha256 and hashlib.sha256(data).hexdigest() != backup.sha256:
        raise BadRequestError("BACKUP_CORRUPTED", "Zaxira nusxa fayli buzilgan (nazorat summasi mos kelmadi).")
    return data


# The super admin must type this exact phrase to confirm a restore (shown in the panel).
RESTORE_CONFIRM_PHRASE = "TIKLASHNI TASDIQLAYMAN"


async def _pg_restore_list(dump_path: Path) -> int:
    """Validate a dump WITHOUT touching any database: read its archive table of contents.

    Proves the file is an intact, restorable custom-format dump. Returns the number of entries.
    """
    settings = get_settings()
    process = await asyncio.create_subprocess_exec(
        settings.pg_restore_path,
        "--list",
        str(dump_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=_PGDUMP_TIMEOUT)
    if process.returncode != 0:
        raise RuntimeError(_scrub(stderr.decode("utf-8", "replace")) or "pg_restore --list failed")
    return sum(1 for line in stdout.decode("utf-8", "replace").splitlines() if line and not line.startswith(";"))


async def _pg_restore_live(dump_path: Path) -> None:  # pragma: no cover - destructive; verified by operators
    """Overwrite the live database from the dump, atomically (all-or-nothing)."""
    settings = get_settings()
    process = await asyncio.create_subprocess_exec(
        settings.pg_restore_path,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--single-transaction",  # the whole restore is one transaction: on any error nothing is changed
        "--dbname",
        _libpq_url(),
        str(dump_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(process.communicate(), timeout=_PGDUMP_TIMEOUT)
    if process.returncode != 0:
        raise RuntimeError(_scrub(stderr.decode("utf-8", "replace")) or "pg_restore failed")


async def restore_backup(
    session: AsyncSession, *, actor_id: uuid.UUID, backup_id: uuid.UUID, confirm: str, live: bool
) -> dict:
    """Safely restore from a backup.

    Always: verify the typed confirmation, decrypt and checksum the dump, take a fresh pre-restore
    safety backup, and validate the dump (read-only). The live overwrite runs only when the operator
    has armed ``allow_in_app_restore`` AND ``live`` is requested — and it is the very last step.
    """
    from app.core.errors import BadRequestError

    if confirm.strip() != RESTORE_CONFIRM_PHRASE:
        raise BadRequestError(
            "RESTORE_NOT_CONFIRMED", f"Tiklashni tasdiqlash uchun «{RESTORE_CONFIRM_PHRASE}» deb yozing."
        )
    backup = await get_backup(session, backup_id)
    if backup.status != BackupStatus.SUCCESS or not backup.storage_key:
        raise BadRequestError("BACKUP_UNAVAILABLE", "Bu zaxira nusxa fayli mavjud emas.")

    # Decrypt (if needed) and verify the checksum before we rely on this dump.
    stored = await get_storage().get(backup.storage_key)
    data = await _plaintext(backup, stored)

    # Safety net first: a pre-restore backup of the current state. Never restore without one.
    pre = await create_backup(session, kind=BackupKind.MANUAL, actor_id=actor_id)
    if pre.status != BackupStatus.SUCCESS:
        raise BadRequestError(
            "RESTORE_PRECHECK_FAILED", "Tiklashdan oldingi xavfsizlik nusxasi olinmadi — tiklash to'xtatildi."
        )

    settings = get_settings()
    live_available = settings.allow_in_app_restore
    with tempfile.TemporaryDirectory(prefix="kitobxon-restore-") as tmp:
        dump_path = Path(tmp) / "restore.dump"
        dump_path.write_bytes(data)
        entries = await _pg_restore_list(dump_path)  # read-only validation; no database is touched

        do_live = live and live_available
        # Record the intent and commit it BEFORE the destructive step, so the audit survives the overwrite.
        record_audit(
            session,
            actor_id=actor_id,
            action="BACKUP_RESTORE",
            entity_type="backup",
            entity_id=backup.id,
            after={"entries": entries, "pre_restore_backup": str(pre.id), "live": do_live},
        )
        await session.commit()
        if do_live:
            await _pg_restore_live(dump_path)  # the last thing we do; restart the app afterwards

    if do_live:
        message = "Baza muvaffaqiyatli tiklandi. Iltimos, ilovani (web + worker) qayta ishga tushiring."
    else:
        message = (
            f"Zaxira nusxa tekshirildi ({entries} ta yozuv) va tiklashdan oldingi xavfsizlik nusxasi olindi. "
            "Jonli bazani almashtirish xavfsizlik uchun o'chirilgan (ALLOW_IN_APP_RESTORE)."
        )
    return {
        "validated": True,
        "entries": entries,
        "pre_restore_backup_id": pre.id,
        "live_restored": do_live,
        "live_available": live_available,
        "message": message,
    }


async def delete_backup(session: AsyncSession, *, actor_id: uuid.UUID, backup_id: uuid.UUID) -> None:
    backup = await get_backup(session, backup_id)
    if backup.storage_key:
        try:
            await get_storage().delete(backup.storage_key)
        except Exception:  # an orphaned file is harmless; the row still goes
            logger.info("A backup file could not be removed from storage")
    await _remove_drive_copy(session, backup)
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


async def _remove_drive_copy(session: AsyncSession, backup: Backup) -> None:
    """Best-effort removal of a backup's Google Drive copy (an orphaned Drive file is harmless)."""
    if not backup.gdrive_file_id:
        return
    try:
        cfg = await gdrive.load_config(session)
        if cfg is not None:
            await gdrive.delete_backup_file(cfg, backup.gdrive_file_id)
    except Exception:
        logger.info("A backup's Google Drive copy could not be removed")


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
            await _remove_drive_copy(session, backup)
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
