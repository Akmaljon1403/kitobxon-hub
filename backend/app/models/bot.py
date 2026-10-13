"""Conversation state of the Telegram bot (aiogram FSM), stored in PostgreSQL.

Keeping it in the database means a half-finished registration survives server restarts
(free hosting plans restart often) and works with several server instances without Redis.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, func
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BotFsmState(Base):
    __tablename__ = "bot_fsm_states"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    state: Mapped[str | None] = mapped_column(String(200))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TextOverride(Base):
    """The owner's own wording of a bot text, a notification or a channel phrase («📝 Matnlar» in the Admin
    Panel): one or several variants, sent in turn. Without a row the wording in the code is used."""

    __tablename__ = "text_overrides"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    variants: Mapped[list[str]] = mapped_column(JSONB)
    rotate: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql_text("true"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
