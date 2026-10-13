from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SettingOut(BaseModel):
    key: str
    group: str
    kind: str
    value: Any
    default: Any
    description: str
    choices: list[str]
    owner_only: bool = False  # changed by the super admins only (money, channels, the club's name)


class SettingUpdateIn(BaseModel):
    value: Any
