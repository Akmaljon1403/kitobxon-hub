"""Referral contests: «who brings the most new readers to the club by <date> wins».

Friends count when they joined the club through a member's personal link between ``starts_at``
and ``ends_at`` and meet the contest's rule (registered, came to an event, or earned points).
Each place has its own prize (points, Premium days, a promo code of a reward, or a prize handed
over in person); the administrator decides what members see while the contest runs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import ContestRule, ContestStatus


class ReferralContest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "referral_contests"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="period_order"),
        CheckConstraint("winners_count BETWEEN 1 AND 50", name="winners_count_range"),
        CheckConstraint("min_friends BETWEEN 1 AND 1000", name="min_friends_range"),
        CheckConstraint("leaderboard_size BETWEEN 0 AND 100", name="leaderboard_size_range"),
        CheckConstraint("name_format IN ('FULL', 'SHORT', 'HIDDEN')", name="name_format_values"),
        Index("ix_referral_contests_status_ends_at", "status", "ends_at"),
    )

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    status: Mapped[ContestStatus] = mapped_column(
        enum_column(ContestStatus), default=ContestStatus.DRAFT, server_default=ContestStatus.DRAFT.value
    )
    # Who counts: friends who only registered, came to an event, or earned some points.
    rule: Mapped[ContestRule] = mapped_column(
        enum_column(ContestRule), default=ContestRule.ATTENDED, server_default=ContestRule.ATTENDED.value
    )
    min_friend_points: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # A member needs at least this many counted friends to win anything.
    min_friends: Mapped[int] = mapped_column(SmallInteger, default=1, server_default=text("1"))
    winners_count: Mapped[int] = mapped_column(SmallInteger, default=3, server_default=text("3"))
    # [{"place": 1, "points": 100, "premium_days": 30, "reward_id": "...", "text": "Kitob"}], one per place.
    prizes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    # Everyone who reaches ``min_friends`` (winners included) gets these points.
    participation_points: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Who may take part (None = everyone); administrators never take part.
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("faculties.id", ondelete="SET NULL"))
    course: Mapped[int | None] = mapped_column(SmallInteger)

    # What members see while it runs.
    show_leaderboard: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    leaderboard_size: Mapped[int] = mapped_column(SmallInteger, default=10, server_default=text("10"))
    show_counts: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    name_format: Mapped[str] = mapped_column(String(8), default="SHORT", server_default=text("'SHORT'"))
    show_my_place: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    show_prizes: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # The table is hidden this many hours before the end (an intrigue for the final day).
    freeze_hours: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))

    # Messages.
    announce: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    remind_hours: Mapped[int] = mapped_column(SmallInteger, default=24, server_default=text("24"))
    announce_results: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    post_to_channel: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    announced_at: Mapped[datetime | None] = mapped_column()
    reminded_at: Mapped[datetime | None] = mapped_column()

    # Members removed from the contest by an administrator: [{"user_id", "reason"}].
    excluded: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    finished_at: Mapped[datetime | None] = mapped_column()
    # Final table: [{"place", "user_id", "name", "friends", "prize": {...}, "handed_over": bool}].
    results: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
