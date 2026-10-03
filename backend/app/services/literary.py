"""Lines from books and proverbs that make the bot sound like a reading club, not a machine.

* ``epigraph(key)`` — a well-known saying about reading (stable for the same key, so a message
  re-rendered for the same member does not change);
* ``book_line(session, book_id, key)`` — a quote from the very book the club is reading, taken
  from the «quotes of the day» already sent (a quote scheduled for a later day is not spoiled).
"""

from __future__ import annotations

import html
import uuid
import zlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BookQuote
from app.models.enums import QuoteStatus

SAYINGS: tuple[tuple[str, str], ...] = (
    ("Bilmaganni so'rab o'rgangan — olim, orlanib so'ramagan — o'ziga zolim.", "Alisher Navoiy"),
    ("Kitobsiz xona — jonsiz tana kabidir.", "Tsitseron"),
    ("Yaxshi kitoblarni o'qish — o'tgan asrlarning eng ulug' insonlari bilan suhbatlashishdir.", "Rene Dekart"),
    ("O'qish aql uchun — badantarbiya tana uchun qanday bo'lsa, shundaydir.", "Jozef Addison"),
    ("Kitob o'qigan inson ming hayot yashaydi.", "Jorj R. R. Martin"),
    ("Bugun kitobxon — ertaga yetakchi.", "Margaret Fuller"),
    ("Kitobdek sodiq do'st yo'q.", "Ernest Xeminguey"),
    ("O'qigan o'zar, o'qimagan to'zar.", "xalq maqoli"),
    ("Yoshlikda olgan bilim — toshga o'yilgan naqsh.", "xalq maqoli"),
    ("Kitob — bilim bulog'i.", "xalq maqoli"),
)


def _index(key: str, size: int) -> int:
    return zlib.crc32(key.encode()) % size


def saying(key: str) -> tuple[str, str]:
    return SAYINGS[_index(key, len(SAYINGS))]


def epigraph(key: str) -> str:
    """«<i>text</i>» — author, ready for an HTML message."""
    text, author = saying(key)
    return f"<i>«{html.escape(text, quote=False)}»</i>\n— {html.escape(author, quote=False)}"


async def book_line(session: AsyncSession, book_id: uuid.UUID | None, key: str) -> str | None:
    """A quote from this book (HTML), or None when the club has none yet."""
    if book_id is None:
        return None
    quotes = list(
        await session.scalars(
            select(BookQuote.text)
            .where(
                BookQuote.book_id == book_id,
                BookQuote.deleted_at.is_(None),
                BookQuote.status == QuoteStatus.SENT,
            )
            .order_by(BookQuote.created_at)
        )
    )
    quotes = [quote.strip() for quote in quotes if quote and len(quote.strip()) <= 400]
    if not quotes:
        return None
    return f"<i>«{html.escape(quotes[_index(key, len(quotes))], quote=False)}»</i>"
