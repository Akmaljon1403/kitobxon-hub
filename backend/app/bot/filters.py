from __future__ import annotations

from typing import Any

from aiogram.filters import Filter
from aiogram.types import TelegramObject

from app.models import User
from app.models.enums import UserStatus


class ActiveMember(Filter):
    """Passes only for registered members whose account is active."""

    async def __call__(self, event: TelegramObject, member: User | None = None, **_: Any) -> bool:
        return member is not None and member.status == UserStatus.ACTIVE


class CanWriteToAdmins(Filter):
    """Registered members who may write to the club: active, waiting for approval, blocked or inactive
    (those who left come back first)."""

    async def __call__(self, event: TelegramObject, member: User | None = None, **_: Any) -> bool:
        return member is not None and member.status in {
            UserStatus.ACTIVE,
            UserStatus.PENDING,
            UserStatus.BLOCKED,
            UserStatus.INACTIVE,
        }
