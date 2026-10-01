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


class SettingUpdateIn(BaseModel):
    value: Any
