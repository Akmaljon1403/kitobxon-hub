"""Books for members: list, details with quotes, and my reading status."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, DbSession
from app.models import Book, BookRead
from app.schemas.book import BookDetailOut, BookOut, MyReading, QuoteOut, ReadingActionIn
from app.schemas.common import Page
from app.services import books as book_service
from app.services.settings import get_setting

router = APIRouter(prefix="/books", tags=["books"])


def book_out(
    book: Book, read: BookRead | None, counts: tuple[int, int] = (0, 0), verification_required: bool = True
) -> BookOut:
    return BookOut(
        id=book.id,
        title=book.title,
        author=book.author,
        description=book.description,
        cover_url=book_service.cover_image(book),
        source_url=book.source_url,
        language=book.language,
        pages=book.pages,
        start_date=book.start_date,
        deadline=book.deadline,
        status=book.status,
        readers_count=counts[0],
        completed_count=counts[1],
        my_reading=MyReading(
            status=read.status,
            started_at=read.started_at,
            completed_at=read.completed_at,
            late=book_service.finished_late(book, read),
            verified=read.verified_at is not None,
            verification_required=verification_required,
        )
        if read
        else None,
    )


@router.get("", response_model=Page[BookOut], summary="Club books (active first)")
async def list_books(
    current: CurrentUserDep,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[BookOut]:
    rows, total = await book_service.list_member_books(db, user_id=current.user.id, limit=limit, offset=offset)
    counts = await book_service.reading_counts(db, [book.id for book, _ in rows])
    required = await get_setting(db, "score.book_completion_requires_verification")
    items = [book_out(book, read, counts.get(book.id, (0, 0)), required) for book, read in rows]
    return Page[BookOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/{book_id}", response_model=BookDetailOut, summary="Book details with quotes")
async def get_book(book_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> BookDetailOut:
    book, read = await book_service.get_member_book(db, user_id=current.user.id, book_id=book_id)
    counts = (await book_service.reading_counts(db, [book.id])).get(book.id, (0, 0))
    quotes = await book_service.book_quotes(db, book.id)
    required = await get_setting(db, "score.book_completion_requires_verification")
    base = book_out(book, read, counts, required)
    return BookDetailOut(
        **base.model_dump(),
        quotes=[QuoteOut(id=q.id, text=q.text, author=q.author, source=q.source) for q in quotes],
    )


@router.post("/{book_id}/reading", response_model=BookOut, summary="I started / I finished reading")
async def set_reading(book_id: uuid.UUID, payload: ReadingActionIn, current: CurrentUserDep, db: DbSession) -> BookOut:
    await book_service.set_reading_status(db, user_id=current.user.id, book_id=book_id, action=payload.action)
    book, read = await book_service.get_member_book(db, user_id=current.user.id, book_id=book_id)
    counts = (await book_service.reading_counts(db, [book.id])).get(book.id, (0, 0))
    return book_out(book, read, counts, await get_setting(db, "score.book_completion_requires_verification"))
