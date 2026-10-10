"""Licences for copies of Kitobxon Hub rented to other organisations.

Every organisation gets its own copy (its own server, database and bot), so the data of different
organisations never meets. The owner signs a licence with a private key that only the owner has
(``python -m app.licence_tool``); the copy checks the signature with the public key and knows the
organisation's name, the end date and the member limit. When the licence ends, members get a polite
«xizmat to'xtatilgan» message, while the administrators can still sign in and download everything.

The club's own server runs without a licence (``LICENCE_REQUIRED`` is off by default).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache

from app.core.config import get_settings

GRACE_DAYS = 7  # after the end date members keep working for a week (time to renew)
MEMBER_MESSAGE = (
    "⏸ Kitobxon Hub xizmati vaqtincha to'xtatilgan. Ma'lumotlaringiz saqlanadi — xizmat qayta ishga "
    "tushgach, hammasi joyida bo'ladi."
)
LIMIT_MESSAGE = "Klub a'zolari soni litsenziya chegarasiga yetgan. Klub rahbariyatiga murojaat qiling."


@dataclass(frozen=True)
class Licence:
    organization: str
    expires: date
    max_members: int | None
    issued: date


@dataclass(frozen=True)
class LicenceStatus:
    required: bool
    valid: bool
    licence: Licence | None
    problem: str | None
    days_left: int | None

    @property
    def blocks_members(self) -> bool:
        if not self.required:
            return False
        if self.licence is None or not self.valid:
            return True
        return self.days_left is not None and self.days_left < -GRACE_DAYS


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def parse(key: str, public_key: str) -> Licence:
    """Check the signature and read the licence. Raises ValueError when it is not genuine."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        body, signature = key.strip().split(".", 1)
        verifier = Ed25519PublicKey.from_public_bytes(_b64decode(public_key.strip()))
        verifier.verify(_b64decode(signature), body.encode("ascii"))
        data = json.loads(_b64decode(body))
        return Licence(
            organization=str(data["org"]),
            expires=date.fromisoformat(data["until"]),
            max_members=int(data["members"]) if data.get("members") else None,
            issued=date.fromisoformat(data["issued"]),
        )
    except (InvalidSignature, ValueError, KeyError, TypeError) as exc:
        raise ValueError("licence is not genuine") from exc


@lru_cache(maxsize=4)
def _parse_cached(key: str, public_key: str) -> Licence:
    return parse(key, public_key)


def sign(private_key_pem: bytes, *, organization: str, until: date, members: int | None) -> str:
    """The owner's side: a licence for one organisation."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    private = load_pem_private_key(private_key_pem, password=None)
    if not isinstance(private, Ed25519PrivateKey):
        raise ValueError("an Ed25519 private key is needed")
    payload = {"org": organization, "until": until.isoformat(), "members": members, "issued": date.today().isoformat()}
    body = b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{b64encode(private.sign(body.encode('ascii')))}"


def status(today: date | None = None) -> LicenceStatus:
    settings = get_settings()
    if not settings.licence_required:
        return LicenceStatus(required=False, valid=True, licence=None, problem=None, days_left=None)
    if settings.licence_key is None or not settings.licence_public_key:
        return LicenceStatus(True, False, None, "Litsenziya kaliti o'rnatilmagan.", None)
    try:
        licence = _parse_cached(settings.licence_key.get_secret_value(), settings.licence_public_key)
    except ValueError:
        return LicenceStatus(True, False, None, "Litsenziya kaliti noto'g'ri.", None)
    today = today or datetime.now().date()
    days_left = (licence.expires - today).days
    problem = None
    if days_left < 0:
        problem = "Litsenziya muddati tugagan." + (
            f" {GRACE_DAYS + days_left} kundan keyin a'zolar uchun xizmat to'xtaydi."
            if days_left >= -GRACE_DAYS
            else ""
        )
    return LicenceStatus(True, True, licence, problem, days_left)


def grace_end(licence: Licence) -> date:
    return licence.expires + timedelta(days=GRACE_DAYS)


async def check_member_limit(session: object) -> None:
    """Registration of a new member: the licence may limit how many members the organisation has."""
    current = status()
    if current.licence is None or current.licence.max_members is None:
        return
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.errors import ForbiddenError
    from app.models import User
    from app.models.enums import UserStatus

    assert isinstance(session, AsyncSession)
    members = await session.scalar(
        select(func.count(User.id)).where(
            User.deleted_at.is_(None), User.status.in_((UserStatus.ACTIVE, UserStatus.PENDING))
        )
    )
    if int(members or 0) >= current.licence.max_members:
        raise ForbiddenError("LICENCE_MEMBER_LIMIT", LIMIT_MESSAGE)
