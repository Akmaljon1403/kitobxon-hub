from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ChannelPostKind, ChannelPostStatus, StickerMood


class ChannelPostTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000, description="Plain text; the post goes out right after")


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
    plain_text: str = Field(description="The text without formatting, for editing")
    in_review: bool = Field(description="Shown to the admins; goes out at scheduled_at unless someone acts")
    reviewed_at: datetime | None = None


class ChannelStickerOut(BaseModel):
    id: uuid.UUID
    emoji: str | None
    set_name: str | None
    is_animated: bool
    mood: StickerMood = StickerMood.ANY
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
