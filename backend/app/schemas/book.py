from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.models.enums import BookStatus, QuoteStatus, ReadingStatus

Url = HttpUrl


def plain(data: dict) -> dict:
    """Pydantic URL objects -> str before they are stored."""
    return {key: str(value) if isinstance(value, HttpUrl) else value for key, value in data.items()}


class BookFields(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    cover_url: Url | None = None
    source_url: Url | None = Field(default=None, description="External link where the book can be read or bought")
    language: str = Field(default="uz", min_length=2, max_length=16)
    pages: int | None = Field(default=None, ge=1, le=10_000)
    start_date: date | None = None
    deadline: date | None = None
    status: BookStatus = BookStatus.DRAFT

    @model_validator(mode="after")
    def _dates(self) -> BookFields:
        if self.start_date and self.deadline and self.deadline < self.start_date:
            raise ValueError("deadline must not be before start_date")
        return self


class BookCreateIn(BookFields):
    pass


class BookUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    author: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    cover_url: Url | None = None
    source_url: Url | None = None
    language: str | None = Field(default=None, min_length=2, max_length=16)
    pages: int | None = Field(default=None, ge=1, le=10_000)
    start_date: date | None = None
    deadline: date | None = None
    status: BookStatus | None = None


class BookBaseOut(BaseModel):
    id: uuid.UUID
    title: str
    author: str
    description: str | None
    cover_url: str | None
    source_url: str | None
    language: str
    pages: int | None
    start_date: date | None
    deadline: date | None
    status: BookStatus
    readers_count: int = 0
    completed_count: int = 0


class BookAdminOut(BookBaseOut):
    created_at: datetime
    updated_at: datetime
    cover_image: str | None = None  # what is shown: the uploaded cover, or the cover link
    cover_uploaded: bool = False


class MyReading(BaseModel):
    status: ReadingStatus
    started_at: datetime
    completed_at: datetime | None
    late: bool = False  # finished after the deadline: in the portfolio, without points
    verified: bool
    # True when book points are only awarded after verification (setting).
    verification_required: bool = True


class BookOut(BookBaseOut):
    my_reading: MyReading | None = None


class QuoteOut(BaseModel):
    id: uuid.UUID
    text: str
    author: str | None
    source: str | None


class BookDetailOut(BookOut):
    quotes: list[QuoteOut]


class ReadingActionIn(BaseModel):
    action: Literal["start", "complete"]


class ReaderOut(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    faculty_name: str | None
    course: int | None
    group_name: str | None
    status: ReadingStatus
    started_at: datetime
    completed_at: datetime | None
    verified_at: datetime | None


class QuoteIn(BaseModel):
    book_id: uuid.UUID | None = None
    text: str = Field(min_length=3, max_length=2000)
    author: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, max_length=255, description="Page or source, e.g. '45-bet'")
    scheduled_date: date | None = None
    status: QuoteStatus = QuoteStatus.DRAFT


class QuoteUpdateIn(BaseModel):
    book_id: uuid.UUID | None = None
    text: str | None = Field(default=None, min_length=3, max_length=2000)
    author: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default=None, max_length=255)
    scheduled_date: date | None = None
    status: QuoteStatus | None = None


class QuoteAdminOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID | None
    book_title: str | None
    text: str
    author: str | None
    source: str | None
    scheduled_date: date | None
    status: QuoteStatus
    sent_at: datetime | None
    created_at: datetime
