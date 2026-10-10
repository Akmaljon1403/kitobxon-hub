"""Posts of the bot in the club's Telegram channel, and stickers admins picked for them."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import ChannelPostKind, ChannelPostStatus, StickerMood


class ChannelPost(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "channel_posts"
    __table_args__ = (Index("ix_channel_posts_status_scheduled_at", "status", "scheduled_at"),)

    kind: Mapped[ChannelPostKind] = mapped_column(enum_column(ChannelPostKind))
    text: Mapped[str] = mapped_column(Text)  # Telegram HTML
    # A picture sent with the text: a file in our storage (book cover, uploaded image) or a URL.
    photo_key: Mapped[str | None] = mapped_column(String(512))
    photo_url: Mapped[str | None] = mapped_column(Text)
    sticker_file_id: Mapped[str | None] = mapped_column(String(255))  # sent right after the post
    # More pictures in our storage: the post goes out as an album (e.g. the photos of a report).
    extra_photo_keys: Mapped[list[str] | None] = mapped_column(JSONB)
    buttons: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)  # [{"text", "url" | "bot_start"}]
    # One post per business fact, e.g. "event:<id>" or "invite:2026-W41".
    dedup_key: Mapped[str | None] = mapped_column(String(160), unique=True)
    status: Mapped[ChannelPostStatus] = mapped_column(
        enum_column(ChannelPostStatus), default=ChannelPostStatus.PENDING, server_default="PENDING"
    )
    scheduled_at: Mapped[datetime] = mapped_column(server_default=func.now())
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    sent_at: Mapped[datetime | None] = mapped_column()
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    last_error: Mapped[str | None] = mapped_column(Text)
    # Automatic posts are shown to the admins first (5 minutes); who approved or edited it, and when.
    review_sent_at: Mapped[datetime | None] = mapped_column()
    reviewed_at: Mapped[datetime | None] = mapped_column()
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ChannelSticker(UUIDPrimaryKeyMixin, Base):
    """Stickers an admin sent to the bot with /stiker; automatic posts end with a random one."""

    __tablename__ = "channel_stickers"

    file_id: Mapped[str] = mapped_column(String(255))
    file_unique_id: Mapped[str] = mapped_column(String(64), unique=True)
    emoji: Mapped[str | None] = mapped_column(String(16))
    set_name: Mapped[str | None] = mapped_column(String(64))
    is_animated: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Which messages it suits (from its emoji): wins, reading, greetings or anything.
    mood: Mapped[StickerMood] = mapped_column(
        enum_column(StickerMood), default=StickerMood.ANY, server_default=StickerMood.ANY.value
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
