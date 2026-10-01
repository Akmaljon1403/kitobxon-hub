"""Achievement definitions (configurable) and achievements unlocked by members."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import AchievementCriteria


class Achievement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "achievements"
    __table_args__ = (
        CheckConstraint("threshold >= 1", name="threshold_positive"),
        CheckConstraint("points >= 0", name="points_non_negative"),
    )

    code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(16), default="🏅", server_default=text("'🏅'"))
    criteria: Mapped[AchievementCriteria] = mapped_column(enum_column(AchievementCriteria))
    threshold: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    # Optional bonus points written to the score ledger when unlocked.
    points: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))


class UserAchievement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id"),
        Index("ix_user_achievements_achievement_id", "achievement_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    achievement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("achievements.id", ondelete="CASCADE"))
    unlocked_at: Mapped[datetime] = mapped_column(server_default=func.now())
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
