"""«📚 Mening mutolaam»: the member's bookshelf, reading diary, the three questions after a book and the
quote box (see ``app.models.reading``).

The shelf holds club books and the member's own books. Putting a club book on «O'qiyapman» or «O'qib
bo'ldim» also marks it in the club list (``BookRead``), so the club's points and achievements keep
working exactly as before. Pages are self-reported: a daily limit keeps the numbers believable, and the
«🛡 Ishonch markazi» shows unusual ones to the admins.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Book, BookQuote, BookReflection, ReadingLog, SavedQuote, ShelfItem, User
from app.models.enums import QuoteStatus, ReadingStatus, ScoreCategory, ShelfStatus
from app.services.settings import get_setting
from app.utils.timezone import local_tz

MAX_NOTE = 1000
MAX_ANSWER = 1500
MIN_ANSWER = 10
MAX_QUOTE = 1000
STATUS_ORDER = {ShelfStatus.READING: 0, ShelfStatus.WANT: 1, ShelfStatus.LATER: 2, ShelfStatus.FINISHED: 3}
STATUS_TITLES = {
    ShelfStatus.WANT: "O'qimoqchiman",
    ShelfStatus.READING: "O'qiyapman",
    ShelfStatus.FINISHED: "O'qib bo'ldim",
    ShelfStatus.LATER: "Keyinroq",
}


def today() -> date:
    return datetime.now(local_tz()).date()


def _month_start() -> datetime:
    return datetime.combine(today().replace(day=1), datetime.min.time(), tzinfo=local_tz())


def _clean(value: str | None, limit: int) -> str | None:
    text = (value or "").strip()
    return text[:limit] if text else None


# ---------------------------------------------------------------------------- the shelf


def _item_query(user_id: uuid.UUID) -> Select[Any]:
    return (
        select(ShelfItem, Book)
        .outerjoin(Book, Book.id == ShelfItem.book_id)
        .where(ShelfItem.user_id == user_id)
        .order_by(ShelfItem.updated_at.desc())
    )


def describe(item: ShelfItem, book: Book | None) -> dict[str, Any]:
    """One shelf item for the apps (club books show their own title, author, cover and pages)."""
    from app.services.books import cover_image

    total = item.pages_total or (book.pages if book else None)
    return {
        "id": item.id,
        "book_id": item.book_id,
        "club_book": book is not None,
        "title": book.title if book else item.title or "—",
        "author": book.author if book else item.author,
        "cover_url": cover_image(book) if book else None,
        "status": item.status,
        "pages_total": total,
        "pages_read": item.pages_read,
        "percent": min(100, round(item.pages_read * 100 / total)) if total else None,
        "rating": item.rating,
        "started_at": item.started_at,
        "finished_at": item.finished_at,
        "updated_at": item.updated_at,
    }


async def shelf(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    rows = (await session.execute(_item_query(user.id))).all()
    items = [describe(item, book) for item, book in rows]
    items.sort(key=lambda entry: STATUS_ORDER.get(entry["status"], 9))
    return items


async def get_item(session: AsyncSession, user: User, item_id: uuid.UUID) -> tuple[ShelfItem, Book | None]:
    row = (await session.execute(_item_query(user.id).where(ShelfItem.id == item_id))).first()
    if row is None:
        raise NotFoundError("SHELF_ITEM_NOT_FOUND", "Bu kitob javoningizda yo'q.")
    return row[0], row[1]


async def _club_reading(session: AsyncSession, user: User, item: ShelfItem, status: ShelfStatus) -> None:
    """A club book on «O'qiyapman» / «O'qib bo'ldim» is marked in the club list too (points as before)."""
    from app.services import books as book_service

    if item.book_id is None or status not in (ShelfStatus.READING, ShelfStatus.FINISHED):
        return
    book = await session.get(Book, item.book_id)
    if book is None or book.status not in book_service.MEMBER_VISIBLE_STATUSES:
        return
    action = "complete" if status == ShelfStatus.FINISHED else "start"
    await book_service.set_reading_status(session, user_id=user.id, book_id=book.id, action=action)


def _set_status(item: ShelfItem, status: ShelfStatus) -> None:
    now = datetime.now(UTC)
    if status in (ShelfStatus.READING, ShelfStatus.FINISHED) and item.started_at is None:
        item.started_at = now
    if status == ShelfStatus.FINISHED and item.finished_at is None:
        item.finished_at = now
    if status != ShelfStatus.FINISHED:
        item.finished_at = None
    item.status = status


async def add(
    session: AsyncSession,
    user: User,
    *,
    book_id: uuid.UUID | None = None,
    title: str | None = None,
    author: str | None = None,
    pages_total: int | None = None,
    status: ShelfStatus = ShelfStatus.WANT,
) -> ShelfItem:
    """Put a club book (``book_id``) or a book of the member's own (``title``) on the shelf."""
    from app.services import books as book_service

    if book_id is not None:
        book = await session.get(Book, book_id)
        if book is None or book.deleted_at is not None or book.status not in book_service.MEMBER_VISIBLE_STATUSES:
            raise NotFoundError("BOOK_NOT_FOUND", "Kitob topilmadi.")
        existing = await session.scalar(
            select(ShelfItem).where(ShelfItem.user_id == user.id, ShelfItem.book_id == book_id)
        )
        if existing is not None:
            raise ConflictError("ALREADY_ON_SHELF", "Bu kitob allaqachon javoningizda.")
        item = ShelfItem(user_id=user.id, book_id=book_id, pages_total=pages_total)
    else:
        clean_title = _clean(title, 255)
        if not clean_title:
            raise BadRequestError("TITLE_REQUIRED", "Kitob nomini yozing.")
        count = await session.scalar(select(func.count()).select_from(ShelfItem).where(ShelfItem.user_id == user.id))
        if (count or 0) >= 500:
            raise ConflictError("SHELF_FULL", "Javoningizda 500 ta kitob bor — keraksizlarini olib tashlang.")
        item = ShelfItem(user_id=user.id, title=clean_title, author=_clean(author, 255), pages_total=pages_total)
    _set_status(item, status)
    session.add(item)
    await session.flush()
    item_id = item.id
    await _club_reading(session, user, item, status)
    await session.commit()
    await _after_change(session, user)
    return (await get_item(session, user, item_id))[0]


async def update(
    session: AsyncSession,
    user: User,
    item_id: uuid.UUID,
    *,
    status: ShelfStatus | None = None,
    pages_total: int | None = None,
    rating: int | None = None,
    clear_rating: bool = False,
) -> ShelfItem:
    item, _ = await get_item(session, user, item_id)
    if pages_total is not None:
        item.pages_total = pages_total
    if rating is not None or clear_rating:
        item.rating = rating
    if status is not None and status != item.status:
        _set_status(item, status)
        await session.flush()
        await _club_reading(session, user, item, status)
    await session.commit()
    await _after_change(session, user)
    return (await get_item(session, user, item_id))[0]


async def remove(session: AsyncSession, user: User, item_id: uuid.UUID) -> None:
    item, _ = await get_item(session, user, item_id)
    await session.delete(item)
    await session.commit()


# ---------------------------------------------------------------------------- the reading diary


async def pages_on(session: AsyncSession, user_id: uuid.UUID, day: date) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(ReadingLog.pages), 0)).where(
            ReadingLog.user_id == user_id, ReadingLog.log_date == day
        )
    )
    return int(total or 0)


async def log_pages(
    session: AsyncSession,
    user: User,
    item_id: uuid.UUID,
    *,
    pages: int,
    minutes: int | None = None,
    note: str | None = None,
    day: date | None = None,
) -> tuple[ReadingLog, ShelfItem]:
    """«Bugun 25 bet o'qidim»: a diary entry; the book moves to «O'qiyapman» by itself."""
    item, _ = await get_item(session, user, item_id)
    day = day or today()
    if day > today() or day < today() - timedelta(days=7):
        raise BadRequestError("LOG_DATE", "Kundalikka faqat oxirgi 7 kun uchun yozish mumkin.")
    if pages <= 0:
        raise BadRequestError("PAGES", "Betlar soni musbat bo'lsin.")
    limit = int(await get_setting(session, "reading.daily_page_limit"))
    already = await pages_on(session, user.id, day)
    if already + pages > limit:
        raise BadRequestError(
            "DAILY_PAGE_LIMIT",
            f"Bir kunda {limit} betdan ko'p yozib bo'lmaydi (bu kunga {already} bet yozilgan).",
        )
    entry = ReadingLog(
        user_id=user.id, shelf_item_id=item.id, log_date=day, pages=pages, minutes=minutes, note=_clean(note, MAX_NOTE)
    )
    session.add(entry)
    item.pages_read += pages
    if item.status in (ShelfStatus.WANT, ShelfStatus.LATER):
        _set_status(item, ShelfStatus.READING)
        await session.flush()
        await _club_reading(session, user, item, ShelfStatus.READING)
    await session.commit()
    await _after_change(session, user)
    await session.refresh(entry)
    return entry, (await get_item(session, user, item_id))[0]


async def delete_log(session: AsyncSession, user: User, log_id: uuid.UUID) -> None:
    entry = await session.scalar(select(ReadingLog).where(ReadingLog.id == log_id, ReadingLog.user_id == user.id))
    if entry is None:
        raise NotFoundError("LOG_NOT_FOUND", "Yozuv topilmadi.")
    item = await session.get(ShelfItem, entry.shelf_item_id)
    if item is not None:
        item.pages_read = max(0, item.pages_read - entry.pages)
    await session.delete(entry)
    await session.commit()


async def diary(
    session: AsyncSession, user: User, *, item_id: uuid.UUID | None = None, limit: int = 60
) -> list[dict[str, Any]]:
    query = (
        select(ReadingLog, ShelfItem, Book)
        .join(ShelfItem, ShelfItem.id == ReadingLog.shelf_item_id)
        .outerjoin(Book, Book.id == ShelfItem.book_id)
        .where(ReadingLog.user_id == user.id)
        .order_by(ReadingLog.log_date.desc(), ReadingLog.created_at.desc())
        .limit(limit)
    )
    if item_id is not None:
        query = query.where(ReadingLog.shelf_item_id == item_id)
    return [
        {
            "id": entry.id,
            "shelf_item_id": item.id,
            "title": book.title if book else item.title or "—",
            "log_date": entry.log_date,
            "pages": entry.pages,
            "minutes": entry.minutes,
            "note": entry.note,
        }
        for entry, item, book in (await session.execute(query)).all()
    ]


def streaks(days: list[date], until: date) -> tuple[int, int]:
    """(current run of reading days ending today or yesterday, the longest run)."""
    unique = sorted(set(days))
    best = run = 0
    previous: date | None = None
    for day in unique:
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    current = 0
    if unique and until - unique[-1] <= timedelta(days=1):
        current = 1
        for index in range(len(unique) - 1, 0, -1):
            if unique[index] - unique[index - 1] == timedelta(days=1):
                current += 1
            else:
                break
    return current, best


async def reading_days(session: AsyncSession, user_id: uuid.UUID, since: date, until: date) -> list[date]:
    rows = await session.scalars(
        select(ReadingLog.log_date)
        .where(ReadingLog.user_id == user_id, ReadingLog.log_date >= since, ReadingLog.log_date <= until)
        .distinct()
    )
    return list(rows)


async def stats(session: AsyncSession, user: User) -> dict[str, Any]:
    """The numbers on top of «📚 Javonim»: today, this week, the streak, books this year, last 14 days."""
    now = today()
    week_start = now - timedelta(days=now.weekday())
    month_start = now.replace(day=1)
    year_start = now.replace(month=1, day=1)
    per_day = dict(
        (
            await session.execute(
                select(ReadingLog.log_date, func.sum(ReadingLog.pages))
                .where(ReadingLog.user_id == user.id, ReadingLog.log_date >= year_start)
                .group_by(ReadingLog.log_date)
            )
        ).all()
    )
    all_days = await reading_days(session, user.id, now - timedelta(days=400), now)
    current, best = streaks(all_days, now)
    finished_year = await session.scalar(
        select(func.count())
        .select_from(ShelfItem)
        .where(
            ShelfItem.user_id == user.id,
            ShelfItem.status == ShelfStatus.FINISHED,
            ShelfItem.finished_at >= datetime.combine(year_start, datetime.min.time(), tzinfo=local_tz()),
        )
    )
    counts = dict(
        (
            await session.execute(
                select(ShelfItem.status, func.count()).where(ShelfItem.user_id == user.id).group_by(ShelfItem.status)
            )
        ).all()
    )
    quotes = await session.scalar(select(func.count()).select_from(SavedQuote).where(SavedQuote.user_id == user.id))
    reflections = await session.scalar(
        select(func.count()).select_from(BookReflection).where(BookReflection.user_id == user.id)
    )

    def total(since: date) -> int:
        return int(sum(pages for day, pages in per_day.items() if day >= since))

    return {
        "today_pages": int(per_day.get(now, 0)),
        "week_pages": total(week_start),
        "month_pages": total(month_start),
        "year_pages": total(year_start),
        "streak": current,
        "best_streak": best,
        "month_days": sum(1 for day in per_day if day >= month_start),
        "finished_this_year": int(finished_year or 0),
        "shelf": {str(status): int(counts.get(status, 0)) for status in ShelfStatus},
        "quotes": int(quotes or 0),
        "reflections": int(reflections or 0),
        "last_days": [
            {"date": now - timedelta(days=offset), "pages": int(per_day.get(now - timedelta(days=offset), 0))}
            for offset in range(13, -1, -1)
        ],
    }


# ---------------------------------------------------------------------------- the three questions


async def reflection(session: AsyncSession, user: User, item_id: uuid.UUID) -> BookReflection | None:
    await get_item(session, user, item_id)
    return await session.scalar(select(BookReflection).where(BookReflection.shelf_item_id == item_id))


async def save_reflection(
    session: AsyncSession, user: User, item_id: uuid.UUID, *, main_idea: str, favorite_moment: str, apply_in_life: str
) -> tuple[BookReflection, int]:
    """«Kitobdan keyin 3 savol». Returns (the answers, points given now — once per book, a few a month)."""
    from app.services.scoring import award_points

    item, book = await get_item(session, user, item_id)
    if item.status != ShelfStatus.FINISHED:
        raise ConflictError("NOT_FINISHED", "Avval kitobni «O'qib bo'ldim» deb belgilang.")
    answers = [_clean(value, MAX_ANSWER) or "" for value in (main_idea, favorite_moment, apply_in_life)]
    if any(len(answer) < MIN_ANSWER for answer in answers):
        raise BadRequestError(
            "ANSWER_TOO_SHORT", f"Har bir savolga kamida {MIN_ANSWER} ta belgidan iborat javob yozing."
        )
    saved = await session.scalar(select(BookReflection).where(BookReflection.shelf_item_id == item.id))
    if saved is None:
        saved = BookReflection(
            user_id=user.id, shelf_item_id=item.id, main_idea="", favorite_moment="", apply_in_life=""
        )
        session.add(saved)
    saved.main_idea, saved.favorite_moment, saved.apply_in_life = answers
    await session.flush()
    points = 0
    if not saved.points_awarded:
        value = int(await get_setting(session, "reading.reflection_points"))
        limit = int(await get_setting(session, "reading.reflection_monthly_limit"))
        given = await session.scalar(
            select(func.count())
            .select_from(BookReflection)
            .where(
                BookReflection.user_id == user.id,
                BookReflection.points_awarded.is_(True),
                BookReflection.updated_at >= _month_start(),
            )
        )
        if value > 0 and (not limit or (given or 0) < limit):
            title = book.title if book else item.title or ""
            awarded = await award_points(
                session,
                user_id=user.id,
                amount=value,
                category=ScoreCategory.CAMPAIGN,
                idempotency_key=f"reflection:{item.id}",
                source_type="REFLECTION",
                source_id=item.id,
                reason=f"«Kitobdan keyin 3 savol»: {title}"[:250],
            )
            if awarded is not None:
                points = value
            saved.points_awarded = True
    await session.commit()
    await _after_change(session, user)
    await session.refresh(saved)
    return saved, points


# ---------------------------------------------------------------------------- the quote box


async def quotes(
    session: AsyncSession, user: User, *, search: str | None = None, item_id: uuid.UUID | None = None
) -> list[SavedQuote]:
    query = select(SavedQuote).where(SavedQuote.user_id == user.id).order_by(SavedQuote.created_at.desc()).limit(300)
    if item_id is not None:
        query = query.where(SavedQuote.shelf_item_id == item_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(SavedQuote.text.ilike(term), SavedQuote.source.ilike(term), SavedQuote.note.ilike(term))
        )
    return list(await session.scalars(query))


async def save_quote(
    session: AsyncSession,
    user: User,
    *,
    text: str | None = None,
    book_quote_id: uuid.UUID | None = None,
    shelf_item_id: uuid.UUID | None = None,
    page: int | None = None,
    note: str | None = None,
) -> SavedQuote:
    """A line the member typed (from a shelf book or anywhere), or a club quote saved with one tap."""
    source: str | None = None
    if book_quote_id is not None:
        club = await session.get(BookQuote, book_quote_id)
        if club is None or club.deleted_at is not None or club.status not in (QuoteStatus.SCHEDULED, QuoteStatus.SENT):
            raise NotFoundError("QUOTE_NOT_FOUND", "Iqtibos topilmadi.")
        known = await session.scalar(
            select(SavedQuote).where(SavedQuote.user_id == user.id, SavedQuote.book_quote_id == book_quote_id)
        )
        if known is not None:
            return known
        book = await session.get(Book, club.book_id) if club.book_id else None
        text = club.text
        source = " — ".join(
            part for part in (club.author or (book.author if book else None), book.title if book else None) if part
        )
        source = source or club.source
    clean = _clean(text, MAX_QUOTE)
    if not clean:
        raise BadRequestError("QUOTE_EMPTY", "Iqtibos matnini yozing.")
    if shelf_item_id is not None:
        item, book = await get_item(session, user, shelf_item_id)
        title = book.title if book else item.title
        writer = book.author if book else item.author
        source = source or " — ".join(part for part in (writer, title) if part)
    count = await session.scalar(select(func.count()).select_from(SavedQuote).where(SavedQuote.user_id == user.id))
    if (count or 0) >= 2000:
        raise ConflictError("QUOTES_FULL", "Sandiqda 2000 ta iqtibos bor — keraksizlarini o'chiring.")
    quote = SavedQuote(
        user_id=user.id,
        shelf_item_id=shelf_item_id,
        book_quote_id=book_quote_id,
        text=clean,
        source=_clean(source, 255),
        page=page,
        note=_clean(note, 500),
    )
    session.add(quote)
    await session.commit()
    await _after_change(session, user)
    await session.refresh(quote)
    return quote


async def get_quote(session: AsyncSession, user: User, quote_id: uuid.UUID) -> SavedQuote:
    quote = await session.scalar(select(SavedQuote).where(SavedQuote.id == quote_id, SavedQuote.user_id == user.id))
    if quote is None:
        raise NotFoundError("QUOTE_NOT_FOUND", "Iqtibos topilmadi.")
    return quote


async def delete_quote(session: AsyncSession, user: User, quote_id: uuid.UUID) -> None:
    await session.execute(delete(SavedQuote).where(SavedQuote.id == quote_id, SavedQuote.user_id == user.id))
    await session.commit()


async def saved_club_quote_ids(session: AsyncSession, user: User, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    rows = await session.scalars(
        select(SavedQuote.book_quote_id).where(SavedQuote.user_id == user.id, SavedQuote.book_quote_id.in_(ids))
    )
    return {row for row in rows if row is not None}


# ---------------------------------------------------------------------------- after every change


async def _after_change(session: AsyncSession, user: User) -> None:
    """Personal missions count what the member just did."""
    from app.services import missions

    await missions.refresh(session, user.id)


async def current_reading(session: AsyncSession, user: User) -> ShelfItem | None:
    """The book the member reads now (the latest one on «O'qiyapman»), for /oqidim in the bot."""
    return await session.scalar(
        select(ShelfItem)
        .where(ShelfItem.user_id == user.id, ShelfItem.status == ShelfStatus.READING)
        .order_by(ShelfItem.updated_at.desc())
        .limit(1)
    )


async def sync_club_book(session: AsyncSession, user_id: uuid.UUID, book_id: uuid.UUID, status: ReadingStatus) -> None:
    """The member pressed «O'qiyapman / O'qidim» on a club book page: the shelf follows (the caller commits)."""
    item = await session.scalar(select(ShelfItem).where(ShelfItem.user_id == user_id, ShelfItem.book_id == book_id))
    wanted = ShelfStatus.FINISHED if status == ReadingStatus.COMPLETED else ShelfStatus.READING
    if item is None:
        item = ShelfItem(user_id=user_id, book_id=book_id)
        session.add(item)
    if item.status != wanted and not (item.status == ShelfStatus.FINISHED and wanted == ShelfStatus.READING):
        _set_status(item, wanted)
