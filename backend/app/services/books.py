"""Books, quotes and members' reading status.

Reading is self-reported ("I started", "I finished"). Book-completion points are written to
the ledger either immediately or only after verification, depending on the setting
``score.book_completion_requires_verification`` (default: after verification).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, NotFoundError
from app.models import Book, BookQuote, BookRead, Faculty, User
from app.models.enums import (
    BookStatus,
    QuoteStatus,
    ReadingStatus,
    ReadingVerification,
    ScoreCategory,
)
from app.services import achievements, announcements
from app.services.audit import record_audit
from app.services.scoring import award_points
from app.services.settings import get_setting
from app.utils.timezone import local_tz

MEMBER_VISIBLE_STATUSES = (BookStatus.ACTIVE, BookStatus.COMPLETED)
_BOOK_FIELDS = (
    "title",
    "author",
    "description",
    "cover_url",
    "source_url",
    "language",
    "pages",
    "start_date",
    "deadline",
    "status",
)

logger = logging.getLogger(__name__)


def _snapshot(book: Book) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in _BOOK_FIELDS:
        value = getattr(book, field)
        result[field] = value.isoformat() if isinstance(value, date) else (str(value) if value is not None else None)
    return result


def _check_dates(start: date | None, deadline: date | None) -> None:
    if start and deadline and deadline < start:
        raise BadRequestError("INVALID_DATES", "Muddat boshlanish sanasidan oldin bo'lishi mumkin emas.")


# ---------------------------------------------------------------------------- admin: books


async def get_book(session: AsyncSession, book_id: uuid.UUID) -> Book:
    book = await session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        raise NotFoundError("BOOK_NOT_FOUND", "Kitob topilmadi.")
    return book


async def reading_counts(session: AsyncSession, book_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    """{book_id: (members reading or finished, members finished)}"""
    if not book_ids:
        return {}
    rows = await session.execute(
        select(
            BookRead.book_id,
            func.count(),
            func.count().filter(BookRead.status == ReadingStatus.COMPLETED),
        )
        .where(BookRead.book_id.in_(book_ids))
        .group_by(BookRead.book_id)
    )
    return {book_id: (int(total), int(done)) for book_id, total, done in rows}


async def list_books_admin(
    session: AsyncSession, *, status: BookStatus | None, search: str | None, limit: int, offset: int
) -> tuple[list[Book], int]:
    conditions = [Book.deleted_at.is_(None)]
    if status:
        conditions.append(Book.status == status)
    if search:
        term = f"%{search.strip()}%"
        conditions.append(Book.title.ilike(term) | Book.author.ilike(term))
    total = await session.scalar(select(func.count()).select_from(Book).where(*conditions))
    rows = await session.scalars(
        select(Book).where(*conditions).order_by(Book.created_at.desc()).limit(limit).offset(offset)
    )
    return list(rows), int(total or 0)


async def create_book(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> Book:
    _check_dates(data.get("start_date"), data.get("deadline"))
    book = Book(**{key: value for key, value in data.items() if key in _BOOK_FIELDS}, created_by=actor_id)
    session.add(book)
    await session.flush()
    record_audit(
        session, actor_id=actor_id, action="BOOK_CREATE", entity_type="book", entity_id=book.id, after=_snapshot(book)
    )
    await announcements.book_published(session, book)
    await session.commit()
    return book


async def update_book(
    session: AsyncSession, *, actor_id: uuid.UUID, book_id: uuid.UUID, changes: dict[str, Any]
) -> Book:
    book = await get_book(session, book_id)
    before = _snapshot(book)
    for field, value in changes.items():
        if field in _BOOK_FIELDS:
            setattr(book, field, value)
    _check_dates(book.start_date, book.deadline)
    after = _snapshot(book)
    if before != after:
        record_audit(
            session,
            actor_id=actor_id,
            action="BOOK_UPDATE",
            entity_type="book",
            entity_id=book.id,
            before=before,
            after=after,
        )
    if before["status"] != BookStatus.ACTIVE and book.status == BookStatus.ACTIVE:
        await announcements.book_published(session, book)
    await session.commit()
    return book


async def delete_book(session: AsyncSession, *, actor_id: uuid.UUID, book_id: uuid.UUID) -> None:
    book = await get_book(session, book_id)
    book.deleted_at = datetime.now(UTC)
    record_audit(
        session, actor_id=actor_id, action="BOOK_DELETE", entity_type="book", entity_id=book.id, before=_snapshot(book)
    )
    await session.commit()


async def list_readers(session: AsyncSession, book_id: uuid.UUID) -> list[tuple[BookRead, User, str | None]]:
    await get_book(session, book_id)
    rows = await session.execute(
        select(BookRead, User, Faculty.name)
        .join(User, User.id == BookRead.user_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .where(BookRead.book_id == book_id, User.deleted_at.is_(None))
        .order_by(
            case((BookRead.status == ReadingStatus.COMPLETED, 0), else_=1),
            BookRead.completed_at.desc().nulls_last(),
            User.last_name,
        )
    )
    return [(read, user, faculty) for read, user, faculty in rows]


async def award_book_completion(session: AsyncSession, read: BookRead, created_by: uuid.UUID | None) -> None:
    # The book still counts as read, but points are given by the deadline rule: when the book has a
    # reading deadline, only finishing on or before it earns points; with no deadline, any time earns them.
    book = await session.get(Book, read.book_id)
    if book is not None and book.deadline is not None:
        finished = (read.completed_at or datetime.now(UTC)).astimezone(local_tz()).date()
        if finished > book.deadline:
            return
    points = await get_setting(session, "score.book_completion_points")
    await award_points(
        session,
        user_id=read.user_id,
        amount=points,
        category=ScoreCategory.BOOK_COMPLETION,
        idempotency_key=f"book:{read.book_id}:user:{read.user_id}",
        source_type="BOOK",
        source_id=read.book_id,
        created_by=created_by,
    )


async def read_at_event(session: AsyncSession, book_id: uuid.UUID | None, user_id: uuid.UUID) -> None:
    """A member attended the discussion of a book: the book counts as read (points once).
    The caller commits."""
    if book_id is None:
        return
    book = await session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        return
    read = await get_or_create_read(session, book_id, user_id)
    now = datetime.now(UTC)
    if read.status != ReadingStatus.COMPLETED:
        read.status = ReadingStatus.COMPLETED
        read.completed_at = now
    if read.verified_at is None:
        read.verified_at = now
        read.verification_source = ReadingVerification.EVENT
    await award_book_completion(session, read, None)


def cover_image(book: Book) -> str | None:
    """The cover to show: the uploaded picture (a public, versioned link) or the cover link."""
    if book.cover_key:
        version = book.cover_key.rsplit("-", 1)[-1].split(".")[0]
        return f"/api/v1/meta/book-covers/{book.id}.jpg?v={version}"
    return book.cover_url


def finished_late(book: Book, read: BookRead) -> bool:
    """Marked as read after the deadline by the member (no points; the club did not confirm it)."""
    if read.status != ReadingStatus.COMPLETED or read.completed_at is None or read.verified_at is not None:
        return False
    return past_deadline(book, read.completed_at)


async def set_cover(session: AsyncSession, *, actor_id: uuid.UUID, book_id: uuid.UUID, data: bytes | None) -> Book:
    """Upload (``data``) or remove (``None``) the book's cover picture."""
    import asyncio

    from app.services.storage import get_storage
    from app.services.test_import import prepare_image

    book = await get_book(session, book_id)
    storage = get_storage()
    old = book.cover_key
    key = None
    if data is not None:
        prepared = await asyncio.to_thread(prepare_image, data)
        key = f"books/covers/{book.id}-{uuid.uuid4().hex[:8]}.jpg"
        await storage.put(key, prepared, "image/jpeg")
    book.cover_key = key
    record_audit(
        session,
        actor_id=actor_id,
        action="BOOK_COVER_SET" if key else "BOOK_COVER_REMOVE",
        entity_type="book",
        entity_id=book.id,
    )
    await session.commit()
    if old and old != key:
        try:
            await storage.delete(old)
        except Exception:  # an orphaned file is harmless
            logger.info("An old book cover could not be removed")
    return book


def past_deadline(book: Book, now: datetime | None = None) -> bool:
    """The book's reading time is over (the deadline day has ended in the club's time zone)."""
    if book.deadline is None:
        return False
    from app.utils.timezone import local_tz

    today = (now or datetime.now(UTC)).astimezone(local_tz()).date()
    return today > book.deadline


async def verify_reading(
    session: AsyncSession, *, actor_id: uuid.UUID, book_id: uuid.UUID, user_id: uuid.UUID
) -> BookRead:
    """Admin confirms that a member read the book (e.g. at the discussion). Awards points once."""
    await get_book(session, book_id)
    member = await session.get(User, user_id)
    if member is None or member.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "Foydalanuvchi topilmadi.")
    read = await get_or_create_read(session, book_id, user_id)
    now = datetime.now(UTC)
    if read.status != ReadingStatus.COMPLETED:
        read.status = ReadingStatus.COMPLETED
        read.completed_at = now
    if read.verified_at is None:
        read.verified_at = now
        read.verified_by = actor_id
        read.verification_source = ReadingVerification.ADMIN
        record_audit(
            session,
            actor_id=actor_id,
            action="BOOK_READ_VERIFY",
            entity_type="book_read",
            entity_id=read.id,
            after={"book_id": str(book_id), "user_id": str(user_id)},
        )
    await award_book_completion(session, read, actor_id)
    await session.flush()
    await achievements.evaluate(session, user_id)
    await session.commit()
    return read


# ---------------------------------------------------------------------------- members


async def get_or_create_read(session: AsyncSession, book_id: uuid.UUID, user_id: uuid.UUID) -> BookRead:
    read = await session.scalar(
        select(BookRead).where(BookRead.book_id == book_id, BookRead.user_id == user_id).with_for_update()
    )
    if read is None:
        read = BookRead(book_id=book_id, user_id=user_id, status=ReadingStatus.READING, started_at=datetime.now(UTC))
        session.add(read)
        await session.flush()
    return read


async def list_member_books(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[tuple[Book, BookRead | None]], int]:
    conditions = [Book.deleted_at.is_(None), Book.status.in_(MEMBER_VISIBLE_STATUSES)]
    total = await session.scalar(select(func.count()).select_from(Book).where(*conditions))
    rows = await session.execute(
        select(Book, BookRead)
        .outerjoin(BookRead, and_(BookRead.book_id == Book.id, BookRead.user_id == user_id))
        .where(*conditions)
        # Active books first, then by nearest deadline, then newest.
        .order_by(
            case((Book.status == BookStatus.ACTIVE, 0), else_=1),
            Book.deadline.asc().nulls_last(),
            Book.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return [(book, read) for book, read in rows], int(total or 0)


async def get_member_book(
    session: AsyncSession, *, user_id: uuid.UUID, book_id: uuid.UUID
) -> tuple[Book, BookRead | None]:
    book = await get_book(session, book_id)
    if book.status not in MEMBER_VISIBLE_STATUSES:
        raise NotFoundError("BOOK_NOT_FOUND", "Kitob topilmadi.")
    read = await session.scalar(select(BookRead).where(BookRead.book_id == book_id, BookRead.user_id == user_id))
    return book, read


async def book_quotes(session: AsyncSession, book_id: uuid.UUID) -> list[BookQuote]:
    rows = await session.scalars(
        select(BookQuote)
        .where(
            BookQuote.book_id == book_id,
            BookQuote.deleted_at.is_(None),
            BookQuote.status.in_((QuoteStatus.SCHEDULED, QuoteStatus.SENT)),
        )
        .order_by(BookQuote.created_at)
    )
    return list(rows)


async def set_reading_status(session: AsyncSession, *, user_id: uuid.UUID, book_id: uuid.UUID, action: str) -> BookRead:
    book = await get_book(session, book_id)
    if book.status not in MEMBER_VISIBLE_STATUSES:
        raise BadRequestError("BOOK_NOT_AVAILABLE", "Bu kitob hozir o'qish uchun ochiq emas.")
    read = await get_or_create_read(session, book_id, user_id)
    from app.services import reading_journal

    if action == "complete" and read.status != ReadingStatus.COMPLETED:
        read.status = ReadingStatus.COMPLETED
        read.completed_at = datetime.now(UTC)
        # Read after the deadline: it goes to the portfolio, but without points.
        on_time = not past_deadline(book)
        if on_time and not await get_setting(session, "score.book_completion_requires_verification"):
            await award_book_completion(session, read, None)
            await session.flush()
            await achievements.evaluate(session, user_id)
    await reading_journal.sync_club_book(session, user_id, book_id, read.status)  # «📚 Javonim» follows
    await session.commit()
    return read


# ---------------------------------------------------------------------------- quotes


def _quote_snapshot(quote: BookQuote) -> dict[str, Any]:
    return {
        "book_id": str(quote.book_id) if quote.book_id else None,
        "text": quote.text,
        "author": quote.author,
        "source": quote.source,
        "scheduled_date": quote.scheduled_date.isoformat() if quote.scheduled_date else None,
        "status": quote.status.value if quote.status else None,
    }


async def get_quote(session: AsyncSession, quote_id: uuid.UUID) -> BookQuote:
    quote = await session.get(BookQuote, quote_id)
    if quote is None or quote.deleted_at is not None:
        raise NotFoundError("QUOTE_NOT_FOUND", "Iqtibos topilmadi.")
    return quote


async def list_quotes(
    session: AsyncSession, *, book_id: uuid.UUID | None, limit: int, offset: int
) -> tuple[list[tuple[BookQuote, str | None]], int]:
    conditions = [BookQuote.deleted_at.is_(None)]
    if book_id:
        conditions.append(BookQuote.book_id == book_id)
    total = await session.scalar(select(func.count()).select_from(BookQuote).where(*conditions))
    rows = await session.execute(
        select(BookQuote, Book.title)
        .outerjoin(Book, Book.id == BookQuote.book_id)
        .where(*conditions)
        .order_by(BookQuote.scheduled_date.desc().nulls_last(), BookQuote.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(quote, title) for quote, title in rows], int(total or 0)


async def _check_quote_date_free(session: AsyncSession, scheduled: date | None, exclude: uuid.UUID | None) -> None:
    if scheduled is None:
        return
    conditions = [
        BookQuote.scheduled_date == scheduled,
        BookQuote.deleted_at.is_(None),
        BookQuote.status != QuoteStatus.ARCHIVED,
    ]
    if exclude:
        conditions.append(BookQuote.id != exclude)
    if await session.scalar(select(func.count()).select_from(BookQuote).where(*conditions)):
        raise BadRequestError("QUOTE_DATE_TAKEN", "Bu sanaga boshqa iqtibos rejalashtirilgan.")


async def create_quote(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> BookQuote:
    if data.get("book_id"):
        await get_book(session, data["book_id"])
    await _check_quote_date_free(session, data.get("scheduled_date"), None)
    quote = BookQuote(**data, created_by=actor_id)
    session.add(quote)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="QUOTE_CREATE",
        entity_type="quote",
        entity_id=quote.id,
        after=_quote_snapshot(quote),
    )
    await session.commit()
    return quote


async def update_quote(
    session: AsyncSession, *, actor_id: uuid.UUID, quote_id: uuid.UUID, changes: dict[str, Any]
) -> BookQuote:
    quote = await get_quote(session, quote_id)
    if changes.get("book_id"):
        await get_book(session, changes["book_id"])
    if "scheduled_date" in changes:
        await _check_quote_date_free(session, changes["scheduled_date"], quote.id)
    before = _quote_snapshot(quote)
    for field, value in changes.items():
        setattr(quote, field, value)
    record_audit(
        session,
        actor_id=actor_id,
        action="QUOTE_UPDATE",
        entity_type="quote",
        entity_id=quote.id,
        before=before,
        after=_quote_snapshot(quote),
    )
    await session.commit()
    return quote


async def delete_quote(session: AsyncSession, *, actor_id: uuid.UUID, quote_id: uuid.UUID) -> None:
    quote = await get_quote(session, quote_id)
    quote.deleted_at = datetime.now(UTC)
    record_audit(
        session,
        actor_id=actor_id,
        action="QUOTE_DELETE",
        entity_type="quote",
        entity_id=quote.id,
        before=_quote_snapshot(quote),
    )
    await session.commit()
