"""Round K2: one order for faculties, courses and groups; the statistics appendix lists the five most
active students only; a new study year moves the course, not the group number."""

from __future__ import annotations

import itertools

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Faculty
from app.models.enums import ScoreCategory
from app.services import documents
from app.services.scoring import award_points
from app.utils.ordering import member_key, natural_key
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role

_ids = itertools.count(2_800_000)


def test_groups_are_counted_by_their_numbers() -> None:
    groups = ["5524", "1001", "301-B", "5424", None, "301-A", "301", "DI-21", "2-guruh", "10-guruh"]
    assert sorted(groups, key=natural_key) == [
        "DI-21",
        "2-guruh",
        "10-guruh",
        "301",
        "301-A",
        "301-B",
        "1001",
        "5424",
        "5524",
        None,
    ]
    # Faculty (by its place in the list, none last) → course → group → surname.
    rows = [
        (2, "Pediatriya", 1, "5524", "A"),
        (1, "Davolash", 2, "5424", "B"),
        (None, None, 1, "101", "C"),
        (1, "Davolash", 1, "5524", "D"),
        (1, "Davolash", 1, "1001", "E"),
    ]
    ordered = sorted(rows, key=lambda row: member_key(*row))
    assert [row[4] for row in ordered] == ["E", "D", "B", "A", "C"]


async def test_statistics_order_and_the_five_most_active(db: AsyncSession) -> None:
    first = Faculty(name="Davolash ishi", short_name="DI", sort_order=1)
    second = Faculty(name="Pediatriya", short_name="PED", sort_order=2)
    db.add_all([second, first])
    await db.flush()
    people = []
    for index, (faculty, course, group) in enumerate(
        [
            (second, 4, "5424"),
            (first, 5, "5524"),
            (first, 4, "5424"),
            (first, 1, "1001"),
            (first, 3, "301"),
            (second, 5, "5524"),
            (first, 3, "301"),
        ]
    ):
        user = await create_user(
            db, telegram_id=next(_ids), faculty_id=faculty.id, course=course, group_name=group, last_name=f"T{index}"
        )
        people.append(user)
        await award_points(
            db, user_id=user.id, amount=10 * (index + 1), category=ScoreCategory.CAMPAIGN, idempotency_key=f"s:{index}"
        )
    await db.commit()

    doc = await documents.statistics(db, documents.Params())
    faculties, courses, groups = doc.tables
    assert [row[0] for row in faculties.rows] == ["Davolash ishi", "Pediatriya"]  # the faculty list order
    assert [row[0] for row in courses.rows] == ["1-kurs", "3-kurs", "4-kurs", "5-kurs"]
    assert [(row[0], row[1]) for row in groups.rows] == [
        ("Davolash ishi", "301"),
        ("Davolash ishi", "1001"),
        ("Davolash ishi", "5424"),
        ("Davolash ishi", "5524"),
        ("Pediatriya", "5424"),
        ("Pediatriya", "5524"),
    ]
    assert groups.rows[0][2] == 2  # two members in 301

    # Points alone do not make a member «active» in the documents (events, tests, books, certificates do),
    # so nobody is in the appendix yet.
    assert doc.appendix == [] and "eng faol 5" in (doc.appendix_title or "")


async def test_the_appendix_has_only_the_top_five(client: httpx.AsyncClient, db: AsyncSession) -> None:
    from datetime import UTC, datetime

    from app.models import BookRead
    from app.models.enums import ReadingStatus
    from tests.factories import create_book

    book = await create_book(db)
    readers = []
    for index in range(8):
        user = await create_user(db, telegram_id=next(_ids), course=2, group_name="201", last_name=f"R{index}")
        readers.append(user)
        db.add(
            BookRead(user_id=user.id, book_id=book.id, status=ReadingStatus.COMPLETED, completed_at=datetime.now(UTC))
        )
        await award_points(
            db, user_id=user.id, amount=5 * (index + 1), category=ScoreCategory.CAMPAIGN, idempotency_key=f"q:{index}"
        )
    await db.commit()

    doc = await documents.statistics(db, documents.Params())
    assert [entry.title.split(" Ism")[0] for entry in doc.appendix] == ["1. R7", "2. R6", "3. R5", "4. R4", "5. R3"]
    assert "40 ball" in doc.appendix[0].details

    boss = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    response = await client.get("/api/v1/admin/documents/statistics/file?format=pdf", headers=admin_headers(boss))
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
