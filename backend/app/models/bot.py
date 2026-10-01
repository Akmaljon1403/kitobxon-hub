"""Conversation state of the Telegram bot (aiogram FSM), stored in PostgreSQL.

Keeping it in the database means a half-finished registration survives server restarts
(free hosting plans restart often) and works with several server instances without Redis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BotFsmState(Base):
    __tablename__ = "bot_fsm_states"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    state: Mapped[str | None] = mapped_column(String(200))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
