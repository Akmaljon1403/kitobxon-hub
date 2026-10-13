"""A member's own reading: the bookshelf, the reading diary, the three questions after a book, the quote
box, and personal missions.

* ``ShelfItem`` — «📚 Javonim»: a club book or any book of the member's own, with a status
  (want / reading / finished / later) and pages read;
* ``ReadingLog`` — «📖 Mutolaa kundaligi»: pages read on a day, with an optional note;
* ``BookReflection`` — «Kitobdan keyin 3 savol»: the main idea, the favourite moment, what to apply;
* ``SavedQuote`` — «💬 Iqtiboslar sandig'i»: lines the member keeps (typed, or a club quote saved);
* ``Mission`` / ``UserMission`` — «🎯 Shaxsiy missiyalar» set by the admins («7 kunda 100 bet»),
  taken by members, progress counted from what they really did.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import MissionMetric, MissionStatus, ShelfStatus, UserMissionStatus


class ShelfItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shelf_items"
    __table_args__ = (
        CheckConstraint("pages_total IS NULL OR pages_total > 0", name="pages_total_positive"),
        CheckConstraint("pages_read >= 0", name="pages_read_not_negative"),
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="rating_range"),
        CheckConstraint("book_id IS NOT NULL OR title IS NOT NULL", name="club_book_or_title"),
        Index("ix_shelf_items_user_id_status", "user_id", "status"),
        Index(
            "uq_shelf_items_user_book",
            "user_id",
            "book_id",
            unique=True,
            postgresql_where=sql_text("book_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    book_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"))
    # A book of the member's own (not in the club list): its title and author.
    title: Mapped[str | None] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ShelfStatus] = mapped_column(
        enum_column(ShelfStatus), default=ShelfStatus.WANT, server_default=ShelfStatus.WANT.value
    )
    pages_total: Mapped[int | None] = mapped_column(Integer)
    pages_read: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    rating: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()


class ReadingLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reading_logs"
    __table_args__ = (
        CheckConstraint("pages > 0 AND pages <= 2000", name="pages_range"),
        CheckConstraint("minutes IS NULL OR (minutes > 0 AND minutes <= 1440)", name="minutes_range"),
        Index("ix_reading_logs_user_id_log_date", "user_id", "log_date"),
        Index("ix_reading_logs_shelf_item_id", "shelf_item_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    shelf_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shelf_items.id", ondelete="CASCADE"))
    log_date: Mapped[date] = mapped_column()
    pages: Mapped[int] = mapped_column(Integer)
    minutes: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)


class BookReflection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "book_reflections"
    __table_args__ = (UniqueConstraint("shelf_item_id"), Index("ix_book_reflections_user_id", "user_id"))

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    shelf_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shelf_items.id", ondelete="CASCADE"))
    main_idea: Mapped[str] = mapped_column(Text)
    favorite_moment: Mapped[str] = mapped_column(Text)
    apply_in_life: Mapped[str] = mapped_column(Text)
    points_awarded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("false"))


class SavedQuote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saved_quotes"
    __table_args__ = (
        CheckConstraint("page IS NULL OR page > 0", name="page_positive"),
        Index("ix_saved_quotes_user_id", "user_id"),
        Index(
            "uq_saved_quotes_user_book_quote",
            "user_id",
            "book_quote_id",
            unique=True,
            postgresql_where=sql_text("book_quote_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    shelf_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shelf_items.id", ondelete="SET NULL"))
    book_quote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("book_quotes.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255))  # «Kitob — Muallif», shown under the quote
    page: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)


class Mission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "missions"
    __table_args__ = (
        CheckConstraint("target > 0", name="target_positive"),
        CheckConstraint("period_days > 0 AND period_days <= 366", name="period_range"),
        CheckConstraint("reward_points >= 0", name="reward_not_negative"),
        Index("ix_missions_status", "status"),
        Index("ix_missions_owner_id", "owner_id"),
    )

    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(16), default="🎯", server_default="🎯")
    metric: Mapped[MissionMetric] = mapped_column(enum_column(MissionMetric))
    target: Mapped[int] = mapped_column(Integer)
    period_days: Mapped[int] = mapped_column(Integer)
    reward_points: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    status: Mapped[MissionStatus] = mapped_column(
        enum_column(MissionStatus), default=MissionStatus.ACTIVE, server_default=MissionStatus.ACTIVE.value
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # A member's own mission («o'zim uchun»): only its owner sees it. Empty for the club's missions.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))


class UserMission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_missions"
    __table_args__ = (
        UniqueConstraint("mission_id", "user_id"),
        Index("ix_user_missions_user_id_status", "user_id", "status"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[UserMissionStatus] = mapped_column(
        enum_column(UserMissionStatus),
        default=UserMissionStatus.ACTIVE,
        server_default=UserMissionStatus.ACTIVE.value,
    )
    started_at: Mapped[datetime] = mapped_column()
    deadline: Mapped[datetime] = mapped_column()
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    completed_at: Mapped[datetime | None] = mapped_column()
    attempts: Mapped[int] = mapped_column(Integer, default=1, server_default=sql_text("1"))
