from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=4096, description="window.Telegram.WebApp.initData")
    scope: Literal["member", "admin"] = "member"


class AdminLinkExchangeRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class AuthUser(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    is_admin: bool
    roles: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
    expires_at: datetime
    scope: Literal["member", "admin"]
    user: AuthUser
