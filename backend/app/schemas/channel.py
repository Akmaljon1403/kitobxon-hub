from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ChannelPostKind, ChannelPostStatus


class ChannelPostOut(BaseModel):
    id: uuid.UUID
    kind: ChannelPostKind
    text: str
    has_photo: bool
    has_sticker: bool
    status: ChannelPostStatus
    scheduled_at: datetime
    sent_at: datetime | None
    last_error: str | None
    manual: bool


class ChannelStickerOut(BaseModel):
    id: uuid.UUID
    emoji: str | None
    set_name: str | None
    is_animated: bool
    created_at: datetime


class ChannelOut(BaseModel):
    enabled: bool
    chat_id: str | None
    link: str | None
    pending: int
    last_sent_at: datetime | None
    last_error: str | None
    posts: list[ChannelPostOut]
    stickers: list[ChannelStickerOut]
