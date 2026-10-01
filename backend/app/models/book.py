"""Books, members' reading status and book quotes.

There is no in-app reader: a book has a title, author, cover and an external link.
Reading status is self-reported and only becomes *verified* through a test, an event
or an admin confirmation.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import BookStatus, QuoteStatus, ReadingStatus, ReadingVerification


class Book(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("pages IS NULL OR pages > 0", name="pages_positive"),
        CheckConstraint("deadline IS NULL OR start_date IS NULL OR deadline >= start_date", name="dates_order"),
        Index("ix_books_status", "status"),
        Index("ix_books_season_id", "season_id"),
    )

    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    # Either an uploaded cover (object storage key) or an external image URL.
    cover_key: Mapped[str | None] = mapped_column(String(512))
    cover_url: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="uz", server_default=sql_text("'uz'"))
    pages: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column()
    deadline: Mapped[date | None] = mapped_column()
    status: Mapped[BookStatus] = mapped_column(
        enum_column(BookStatus), default=BookStatus.DRAFT, server_default=BookStatus.DRAFT.value
    )
    season_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class BookRead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "book_reads"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id"),
        Index("ix_book_reads_book_id_status", "book_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"))
    status: Mapped[ReadingStatus] = mapped_column(
        enum_column(ReadingStatus), default=ReadingStatus.READING, server_default=ReadingStatus.READING.value
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column()
    verified_at: Mapped[datetime | None] = mapped_column()
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verification_source: Mapped[ReadingVerification | None] = mapped_column(enum_column(ReadingVerification))


class BookQuote(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Quotes are entered by admins (never generated) and can be scheduled as "quote of the day"."""

    __tablename__ = "book_quotes"
    __table_args__ = (
        Index("ix_book_quotes_book_id", "book_id"),
        Index(
            "uq_book_quotes_scheduled_date",
            "scheduled_date",
            unique=True,
            postgresql_where=sql_text("scheduled_date IS NOT NULL AND deleted_at IS NULL AND status <> 'ARCHIVED'"),
        ),
    )

    book_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(255))
    scheduled_date: Mapped[date | None] = mapped_column()
    status: Mapped[QuoteStatus] = mapped_column(
        enum_column(QuoteStatus), default=QuoteStatus.DRAFT, server_default=QuoteStatus.DRAFT.value
    )
    sent_at: Mapped[datetime | None] = mapped_column()
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
