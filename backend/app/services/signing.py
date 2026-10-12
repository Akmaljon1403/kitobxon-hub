"""Who signs the club's documents, and the seal stamped over the signature — the same on every paper.

The ma'lumotnoma, the lists and statistics for the institute, the portfolio, the official reports and the
certificates all end with «Klub rahbari: ____ Ism Familiya» and the club's round seal (``app/brand/seal.png``)
pressed over the signature line, as on a stamped paper.

The name is the setting ``certificates.signer_name``; when it is empty, the club leader is the first super
admin (the owner) — so a document never comes out with an empty «Klub rahbari:».
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role, User, UserRole
from app.models.enums import SystemRole, UserStatus
from app.services import brand
from app.services.settings import get_setting
from app.utils.timezone import local_tz


@dataclass(frozen=True)
class Signer:
    title: str  # «Klub rahbari»
    name: str  # «Akmaljon Bahodirov» (may be empty only when the club has no super admin at all)
    seal: str | None  # the seal picture (data URI) or None when switched off / not supplied

    @property
    def line(self) -> str:
        """«Klub rahbari: ____________ Akmaljon Bahodirov» — for files without pictures (Excel)."""
        return f"{self.title}: ____________________ {self.name}".rstrip()


async def owner_name(session: AsyncSession) -> str:
    """The first super admin's «Ism Familiya» (the club leader when nobody else is named)."""
    row = (
        await session.execute(
            select(User.first_name, User.last_name)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.code == SystemRole.SUPER_ADMIN, User.deleted_at.is_(None), User.status == UserStatus.ACTIVE)
            .order_by(UserRole.granted_at, User.created_at)
            .limit(1)
        )
    ).first()
    if row is None:
        return ""
    first, last = row
    return f"{first} {last or ''}".strip()


async def signer(session: AsyncSession) -> Signer:
    title = str(await get_setting(session, "certificates.signer_title") or "").strip() or "Klub rahbari"
    name = str(await get_setting(session, "certificates.signer_name") or "").strip() or await owner_name(session)
    seal = brand.seal(bool(await get_setting(session, "certificates.seal")), "#ffffff")
    return Signer(title=title, name=name, seal=seal)


def issued_now() -> str:
    """«12.10.2026, soat 20:45» — when the paper was made (the club's time)."""
    now = datetime.now(local_tz())
    return f"{now:%d.%m.%Y}, soat {now:%H:%M}"
