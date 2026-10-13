"""«Kitobxonlik portfoliosi»: everything a member achieved in the club in one PDF (a Premium perk).

Useful for a CV, a scholarship or a grant application: books read, events attended, test results,
certificates (with their check codes) and achievements, with a QR code to the live results page.
"""

from __future__ import annotations

import asyncio
from typing import Any

import segno
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttendanceRecord, Book, BookRead, Certificate, Event, Faculty, Test, TestAttempt, User
from app.models.enums import AttemptStatus, AttendanceStatus, ReadingStatus
from app.services import signing
from app.services.settings import get_setting
from app.utils.timezone import format_date


def filename(user: User) -> str:
    from app.services.passport import member_number

    return f"Kitobxonlik-portfoliosi-{member_number(user)}.pdf"


async def collect(session: AsyncSession, user: User) -> dict[str, Any]:
    from app.services import achievements, quizzes, ranking
    from app.services import passport as passport_service

    faculty = (
        await session.scalar(select(Faculty.name).where(Faculty.id == user.faculty_id)) if user.faculty_id else None
    )
    books = (
        await session.execute(
            select(Book.title, Book.author, BookRead.completed_at, BookRead.verified_at)
            .join(Book, Book.id == BookRead.book_id)
            .where(BookRead.user_id == user.id, BookRead.status == ReadingStatus.COMPLETED)
            .order_by(BookRead.completed_at.desc().nulls_last())
        )
    ).all()
    events = (
        await session.execute(
            select(Event.title, Event.starts_at)
            .join(AttendanceRecord, AttendanceRecord.event_id == Event.id)
            .where(AttendanceRecord.user_id == user.id, AttendanceRecord.status == AttendanceStatus.VERIFIED)
            .order_by(Event.starts_at.desc())
        )
    ).all()
    best = (
        select(TestAttempt.test_id, func.max(TestAttempt.score).label("score"))
        .where(
            TestAttempt.user_id == user.id,
            TestAttempt.status.in_((AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)),
        )
        .group_by(TestAttempt.test_id)
        .subquery()
    )
    tests = []
    for test, score in (
        await session.execute(
            select(Test, best.c.score).join(best, best.c.test_id == Test.id).order_by(Test.starts_at.desc())
        )
    ).all():
        place = next(
            (row["place"] for row in await quizzes.test_standings(session, test) if row["user_id"] == user.id), None
        )
        tests.append(
            {
                "title": test.title,
                "date": format_date(test.starts_at),
                "score": int(score or 0),
                "max": test.max_score,
                "passed": quizzes.passed(test, score),
                "place": place if place and place <= 3 else None,
            }
        )
    certificates = list(
        await session.scalars(
            select(Certificate)
            .where(Certificate.user_id == user.id, Certificate.revoked_at.is_(None))
            .order_by(Certificate.issued_at.desc())
        )
    )
    from app.services.certificates import display_code

    earned = [item for item in await achievements.member_achievements(session, user.id) if item["unlocked_at"]]
    summary = await ranking.score_summary(session, user.id)
    overall = await ranking.ranking(session, period="all", scope="all", viewer=user, limit=1)
    since = user.registered_at or user.created_at
    verify = passport_service.verify_url(passport_service.verify_code(user))
    return {
        "organization": await get_setting(session, "org.organization_name"),
        "club": await get_setting(session, "org.club_name"),
        "name": f"{user.last_name} {user.first_name}",
        "number": passport_service.member_number(user),
        "faculty": faculty,
        "course": user.course,
        "group": user.group_name,
        "since": format_date(since) if since else "—",
        "generated": signing.issued_now(),
        "signer": await signing.signer(session),
        "points": summary["total"],
        "rank": overall.me.rank if overall.me else None,
        "books": [
            {
                "title": title,
                "author": author,
                "date": format_date(completed) if completed else "—",
                "verified": verified is not None,
            }
            for title, author, completed, verified in books
        ],
        "events": [{"title": title, "date": format_date(starts_at)} for title, starts_at in events],
        "tests": tests,
        "certificates": [
            {"title": c.title, "date": format_date(c.issued_at), "code": display_code(c.verify_code)}
            for c in certificates
        ],
        "achievements": [
            {"title": item["title"], "description": item["description"], "date": format_date(item["unlocked_at"])}
            for item in earned
        ],
        "qr": segno.make(verify, error="m").svg_data_uri(dark="#14402c", border=0) if verify else None,
        "verify": verify,
    }


async def render_pdf(session: AsyncSession, user: User) -> bytes:
    from weasyprint import HTML  # heavy import, only when a PDF is needed

    from app.services.report_pdf import TEMPLATES, _environment

    html = _environment().get_template("portfolio.html").render(**await collect(session, user))
    return await asyncio.to_thread(lambda: HTML(string=html, base_url=str(TEMPLATES)).write_pdf())
