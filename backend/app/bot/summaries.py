"""Short, personal summaries for the bot's menu sections.

The bot answers each menu button with two or three lines (the most useful fact for this member)
and a button to the Mini App page with the details. The numbers come from the same services the
Mini App uses, so both always agree.
"""

from __future__ import annotations

import html
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.models import AttendanceSession, Faculty, SupportTicket, User
from app.models.enums import AttendanceSessionStatus, BookStatus, ReadingStatus, UserStatus
from app.services import achievements as achievement_service
from app.services import attendance as attendance_service
from app.services import books as book_service
from app.services import certificates as certificate_service
from app.services import events as event_service
from app.services import passport as passport_service
from app.services import quizzes as quiz_service
from app.services import ranking as ranking_service
from app.utils.timezone import format_date, format_human, format_human_date, local_tz

MEDALS = ("🥇", "🥈", "🥉")


def _e(value: str | None) -> str:
    return html.escape(value or "", quote=False)


def days_left(deadline: date, today: date | None = None) -> str:
    today = today or datetime.now(local_tz()).date()
    days = (deadline - today).days
    if days < 0:
        return "muddati o'tgan"
    if days == 0:
        return "bugun oxirgi kun"
    return f"{days} kun qoldi"


async def books(session: AsyncSession, member: User) -> str:
    rows, _ = await book_service.list_member_books(session, user_id=member.id, limit=20, offset=0)
    active = [(book, read) for book, read in rows if book.status == BookStatus.ACTIVE]
    if not active:
        return texts.BOOKS_NONE
    book, read = active[0]
    if read is None:
        status = texts.BOOKS_STATUS_NOT_STARTED
    elif read.status == ReadingStatus.COMPLETED:
        status = texts.BOOKS_STATUS_VERIFIED if read.verified_at else texts.BOOKS_STATUS_DONE
    else:
        status = texts.BOOKS_STATUS_READING
    deadline = (
        texts.BOOKS_DEADLINE.format(date=format_human_date(book.deadline), left=days_left(book.deadline))
        if book.deadline
        else ""
    )
    text = texts.BOOKS_CURRENT.format(title=_e(book.title), author=_e(book.author), deadline=deadline, status=status)
    if len(active) > 1:
        text += texts.BOOKS_MORE.format(count=len(active) - 1)
    return text


async def events(session: AsyncSession, member: User) -> str:
    rows, total = await event_service.list_member_events(
        session, user_id=member.id, scope="upcoming", limit=1, offset=0
    )
    if not rows:
        return texts.EVENTS_NONE
    event, registration, _ = rows[0]
    text = texts.EVENTS_NEXT.format(
        title=_e(event.title),
        when=format_human(event.starts_at),
        where=texts.EVENTS_WHERE.format(location=_e(event.location)) if event.location else "",
        registration=texts.EVENTS_REGISTERED if registration is not None else texts.EVENTS_NOT_REGISTERED,
    )
    if total > 1:
        text += texts.EVENTS_MORE.format(count=total)
    return text


async def attendance(session: AsyncSession, member: User) -> tuple[str, bool]:
    """(text, whether a QR/code can be entered right now)."""
    live = await attendance_service.live_events_for_member(session, member.id)
    pending = [item for item in live if not item["checked_in"]]
    if pending:
        return texts.ATTENDANCE_OPEN.format(title=_e(pending[0]["title"])), True
    if live:
        return texts.ATTENDANCE_ALREADY.format(title=_e(live[0]["title"])), False
    rows, _ = await event_service.list_member_events(session, user_id=member.id, scope="upcoming", limit=1, offset=0)
    upcoming = (
        texts.ATTENDANCE_NEXT.format(title=_e(rows[0][0].title), when=format_human(rows[0][0].starts_at))
        if rows
        else ""
    )
    return texts.ATTENDANCE_NONE.format(next=upcoming), False


async def tests(session: AsyncSession, member: User) -> str:
    all_tests = await quiz_service.list_member_tests(session, user_id=member.id)
    now = datetime.now(UTC)
    open_tests = [test for test in all_tests if quiz_service.state(test, now) == "OPEN"]
    if not open_tests:
        upcoming = [test for test in all_tests if quiz_service.state(test, now) == "UPCOMING"]
        if upcoming:
            return texts.TESTS_UPCOMING.format(title=_e(upcoming[0].title), starts=format_human(upcoming[0].starts_at))
        return texts.TESTS_NONE
    test = open_tests[0]
    attempts = (await quiz_service.my_attempts(session, user_id=member.id, test_ids=[test.id])).get(test.id, [])
    scores = [attempt.score for attempt in attempts if attempt.score is not None]
    text = texts.TESTS_OPEN.format(
        title=_e(test.title),
        max_score=test.max_score,
        minutes=test.duration_minutes,
        ends=format_human(test.ends_at),
        status=texts.TESTS_DONE.format(score=max(scores)) if scores else texts.TESTS_NOT_DONE,
    )
    if len(open_tests) > 1:
        text += texts.TESTS_MORE.format(count=len(open_tests) - 1)
    return text


async def results(session: AsyncSession, member: User) -> str:
    summary = await ranking_service.score_summary(session, member.id)
    if summary["total"] == 0 and not summary["breakdown"]:
        return texts.RESULTS_EMPTY
    overall = await ranking_service.ranking(session, period="all", scope="all", viewer=member, limit=1)
    monthly = await ranking_service.ranking(session, period="month", scope="all", viewer=member, limit=1)
    breakdown = summary["breakdown"]
    return texts.RESULTS.format(
        total=summary["total"],
        rank_all=texts.RESULTS_RANK.format(rank=overall.me.rank) if overall.me else "",
        month=monthly.me.total if monthly.me else 0,
        rank_month=texts.RESULTS_RANK.format(rank=monthly.me.rank) if monthly.me else "",
        attendance=breakdown.get("ATTENDANCE", 0),
        tests=breakdown.get("TEST", 0) + breakdown.get("TEST_RANK_BONUS", 0),
        books=breakdown.get("BOOK_COMPLETION", 0),
    )


async def ranking(session: AsyncSession, member: User) -> str:
    board = await ranking_service.ranking(session, period="month", scope="all", viewer=member, limit=3)
    if not board.items:
        return texts.RANKING_EMPTY
    top = "\n".join(
        texts.RANKING_ROW.format(medal=MEDALS[index], name=_e(row.name), total=row.total)
        for index, row in enumerate(board.items[:3])
    )
    me = texts.RANKING_ME.format(rank=board.me.rank, total=board.me.total) if board.me else texts.RANKING_ME_NONE
    return texts.RANKING.format(top=top, me=me)


async def achievements(session: AsyncSession, member: User) -> str:
    items = await achievement_service.member_achievements(session, member.id)
    if not items:
        return texts.ACHIEVEMENTS_NONE
    unlocked = sorted((item for item in items if item["unlocked_at"]), key=lambda item: item["unlocked_at"])
    upcoming = [
        item
        for item in items
        if not item["unlocked_at"] and item["progress"] is not None and item["progress"] < item["threshold"]
    ]
    upcoming.sort(key=lambda item: item["progress"] / max(item["threshold"], 1), reverse=True)
    last = (
        texts.ACHIEVEMENTS_LAST.format(icon=unlocked[-1]["icon"] or "🏅", title=_e(unlocked[-1]["title"]))
        if unlocked
        else ""
    )
    nxt = (
        texts.ACHIEVEMENTS_NEXT.format(
            icon=upcoming[0]["icon"] or "🎯",
            title=_e(upcoming[0]["title"]),
            progress=upcoming[0]["progress"],
            threshold=upcoming[0]["threshold"],
        )
        if upcoming
        else ""
    )
    count = await certificate_service.count_for_member(session, member.id)
    certificates = texts.ACHIEVEMENTS_CERTIFICATES.format(count=count) if count else ""
    return texts.ACHIEVEMENTS.format(
        done=len(unlocked), total=len(items), last=last, next=nxt, certificates=certificates
    )


def member_number(member: User) -> str:
    return passport_service.member_number(member)


async def passport(session: AsyncSession, member: User) -> str:
    faculty = (
        await session.scalar(select(Faculty.name).where(Faculty.id == member.faculty_id)) if member.faculty_id else None
    )
    summary = await ranking_service.score_summary(session, member.id)
    return texts.PASSPORT.format(
        number=member_number(member),
        first_name=_e(member.first_name),
        last_name=_e(member.last_name),
        faculty=_e(faculty) or texts.NO_FACULTY,
        course=member.course or "—",
        group=_e(member.group_name) or "—",
        registered=format_date(member.registered_at),
        total=summary["total"],
    )


async def admin_home(session: AsyncSession) -> str:
    members = await session.scalar(
        select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
    )
    since = datetime.now(local_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = await session.scalar(
        select(func.count()).select_from(User).where(User.registered_at >= since, User.deleted_at.is_(None))
    )
    tickets = await session.scalar(
        select(func.count()).select_from(SupportTicket).where(SupportTicket.unread_for_admin.is_(True))
    )
    await attendance_service.open_scheduled_sessions(session)
    open_attendance = await session.scalar(
        select(func.count())
        .select_from(AttendanceSession)
        .where(
            AttendanceSession.status == AttendanceSessionStatus.OPEN,
            AttendanceSession.closes_at > datetime.now(UTC),
        )
    )
    return texts.ADMIN_HOME.format(
        members=members or 0,
        new_today=texts.ADMIN_NEW_TODAY.format(count=new_today) if new_today else "",
        tickets=tickets or 0,
        open_attendance=open_attendance or 0,
    )
