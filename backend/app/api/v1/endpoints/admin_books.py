"""Admin Panel: books, readers and quotes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models import Book, BookQuote
from app.models.enums import BookStatus
from app.schemas.book import (
    BookAdminOut,
    BookCreateIn,
    BookUpdateIn,
    QuoteAdminOut,
    QuoteIn,
    QuoteUpdateIn,
    ReaderOut,
    plain,
)
from app.schemas.common import Page
from app.security.permissions import Perm
from app.services import books as book_service

router = APIRouter(prefix="/admin", tags=["admin: books"])
BookViewer = Annotated[CurrentUser, Depends(require_permissions(Perm.BOOK_VIEW))]
BookCreator = Annotated[CurrentUser, Depends(require_permissions(Perm.BOOK_CREATE))]
BookEditor = Annotated[CurrentUser, Depends(require_permissions(Perm.BOOK_EDIT))]
BookDeleter = Annotated[CurrentUser, Depends(require_permissions(Perm.BOOK_DELETE))]


def _book_out(book: Book, counts: tuple[int, int] = (0, 0)) -> BookAdminOut:
    return BookAdminOut(
        id=book.id,
        title=book.title,
        author=book.author,
        description=book.description,
        cover_url=book.cover_url,
        source_url=book.source_url,
        language=book.language,
        pages=book.pages,
        start_date=book.start_date,
        deadline=book.deadline,
        status=book.status,
        readers_count=counts[0],
        completed_count=counts[1],
        created_at=book.created_at,
        updated_at=book.updated_at,
    )


async def _with_counts(db, book: Book) -> BookAdminOut:
    counts = (await book_service.reading_counts(db, [book.id])).get(book.id, (0, 0))
    return _book_out(book, counts)


@router.get("/books", response_model=Page[BookAdminOut], summary="All books including drafts")
async def list_books(
    _: BookViewer,
    db: DbSession,
    status_filter: Annotated[BookStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[BookAdminOut]:
    books, total = await book_service.list_books_admin(
        db, status=status_filter, search=search, limit=limit, offset=offset
    )
    counts = await book_service.reading_counts(db, [book.id for book in books])
    items = [_book_out(book, counts.get(book.id, (0, 0))) for book in books]
    return Page[BookAdminOut](items=items, total=total, limit=limit, offset=offset)


@router.post("/books", response_model=BookAdminOut, status_code=status.HTTP_201_CREATED, summary="Add a book")
async def create_book(payload: BookCreateIn, current: BookCreator, db: DbSession) -> BookAdminOut:
    book = await book_service.create_book(db, actor_id=current.user.id, data=plain(payload.model_dump()))
    return await _with_counts(db, book)


@router.get("/books/{book_id}", response_model=BookAdminOut, summary="Book details")
async def get_book(book_id: uuid.UUID, _: BookViewer, db: DbSession) -> BookAdminOut:
    return await _with_counts(db, await book_service.get_book(db, book_id))


@router.patch("/books/{book_id}", response_model=BookAdminOut, summary="Edit, publish or archive a book")
async def update_book(book_id: uuid.UUID, payload: BookUpdateIn, current: BookEditor, db: DbSession) -> BookAdminOut:
    book = await book_service.update_book(
        db, actor_id=current.user.id, book_id=book_id, changes=plain(payload.model_dump(exclude_unset=True))
    )
    return await _with_counts(db, book)


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a book (soft)")
async def delete_book(book_id: uuid.UUID, current: BookDeleter, db: DbSession) -> Response:
    await book_service.delete_book(db, actor_id=current.user.id, book_id=book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/books/{book_id}/readers", response_model=list[ReaderOut], summary="Who is reading / finished")
async def readers(book_id: uuid.UUID, _: BookViewer, db: DbSession) -> list[ReaderOut]:
    return [
        ReaderOut(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            faculty_name=faculty,
            course=user.course,
            group_name=user.group_name,
            status=read.status,
            started_at=read.started_at,
            completed_at=read.completed_at,
            verified_at=read.verified_at,
        )
        for read, user, faculty in await book_service.list_readers(db, book_id)
    ]


@router.post(
    "/books/{book_id}/readers/{user_id}/verify",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirm that a member read the book (awards book points once)",
)
async def verify_reader(book_id: uuid.UUID, user_id: uuid.UUID, current: BookEditor, db: DbSession) -> Response:
    await book_service.verify_reading(db, actor_id=current.user.id, book_id=book_id, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------- quotes


def _quote_out(quote: BookQuote, book_title: str | None) -> QuoteAdminOut:
    return QuoteAdminOut(
        id=quote.id,
        book_id=quote.book_id,
        book_title=book_title,
        text=quote.text,
        author=quote.author,
        source=quote.source,
        scheduled_date=quote.scheduled_date,
        status=quote.status,
        sent_at=quote.sent_at,
        created_at=quote.created_at,
    )


async def _quote_with_title(db, quote: BookQuote) -> QuoteAdminOut:
    title = (await book_service.get_book(db, quote.book_id)).title if quote.book_id else None
    return _quote_out(quote, title)


@router.get("/quotes", response_model=Page[QuoteAdminOut], summary="Quotes")
async def list_quotes(
    _: BookViewer,
    db: DbSession,
    book_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[QuoteAdminOut]:
    rows, total = await book_service.list_quotes(db, book_id=book_id, limit=limit, offset=offset)
    return Page[QuoteAdminOut](
        items=[_quote_out(quote, title) for quote, title in rows], total=total, limit=limit, offset=offset
    )


@router.post("/quotes", response_model=QuoteAdminOut, status_code=status.HTTP_201_CREATED, summary="Add a quote")
async def create_quote(payload: QuoteIn, current: BookCreator, db: DbSession) -> QuoteAdminOut:
    quote = await book_service.create_quote(db, actor_id=current.user.id, data=payload.model_dump())
    return await _quote_with_title(db, quote)


@router.patch("/quotes/{quote_id}", response_model=QuoteAdminOut, summary="Edit or schedule a quote")
async def update_quote(
    quote_id: uuid.UUID, payload: QuoteUpdateIn, current: BookEditor, db: DbSession
) -> QuoteAdminOut:
    quote = await book_service.update_quote(
        db, actor_id=current.user.id, quote_id=quote_id, changes=payload.model_dump(exclude_unset=True)
    )
    return await _quote_with_title(db, quote)


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a quote")
async def delete_quote(quote_id: uuid.UUID, current: BookDeleter, db: DbSession) -> Response:
    await book_service.delete_quote(db, actor_id=current.user.id, quote_id=quote_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
