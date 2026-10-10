"""Knowledge tests ("Testlar"): admin editor, member attempts, server-side grading and points.

Rules (docs/ARCHITECTURE.md §7.3 and §8):
- Correct answers never leave the server until the test has closed.
- The server fixes each attempt's deadline when it starts: min(start + duration, test end).
  Answers that arrive after the deadline (plus a few seconds for the network) are rejected.
- Grading: an answer is correct when the selected options are exactly the correct ones
  (single choice: the one correct option; multiple choice: all-or-nothing).
  Test score = round(earned question points / all question points × test.max_score).
- A score below the passing score earns no points. With several attempts the best one counts:
  every better attempt adds only the difference to the ledger.
- Passing a test linked to a book verifies that the member read the book.
- After the test closes, the top places receive the bonuses from ``score.test_rank_bonus``.
"""

from __future__ import annotations

import io
import logging
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import (
    AttendanceRecord,
    Book,
    Faculty,
    ScoreTransaction,
    Test,
    TestActivityLog,
    TestAnswer,
    TestAttempt,
    TestOption,
    TestQuestion,
    User,
)
from app.models.enums import (
    AttemptStatus,
    AttendanceStatus,
    QuestionType,
    ReadingStatus,
    ReadingVerification,
    ScoreCategory,
    TestActivityType,
    TestStatus,
)
from app.services import achievements, announcements
from app.services import certificates as certificate_service
from app.services.audit import record_audit
from app.services.books import award_book_completion, get_or_create_read
from app.services.scoring import award_points, current_season_id
from app.services.settings import get_setting
from app.services.storage import get_storage
from app.utils.spreadsheet import excel_writer
from app.utils.timezone import format_datetime

logger = logging.getLogger(__name__)

MEMBER_VISIBLE = (TestStatus.PUBLISHED, TestStatus.CLOSED)
FINISHED = (AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)
# Requests already on their way when the timer hits zero are still accepted.
NETWORK_GRACE = timedelta(seconds=5)
# Average seconds per answered question below which the attempt gets a FAST_ANSWER signal.
FAST_ANSWER_SECONDS = 3
# Signals that only mark a return to normal are not counted as suspicious.
NEUTRAL_SIGNALS = (
    TestActivityType.VISIBILITY_VISIBLE,
    TestActivityType.FOCUS_GAINED,
    TestActivityType.RETURNED,
)
_TEST_FIELDS = (
    "title",
    "description",
    "book_id",
    "starts_at",
    "ends_at",
    "duration_minutes",
    "max_score",
    "passing_score",
    "attempts_allowed",
    "shuffle_questions",
    "shuffle_options",
)
# Changing these after someone has answered would make results incomparable.
_LOCKED_AFTER_ATTEMPTS = ("max_score", "passing_score")
_random = random.SystemRandom()


def _now() -> datetime:
    return datetime.now(UTC)


def state(test: Test, now: datetime | None = None) -> str:
    """UPCOMING / OPEN / CLOSED as members see it (DRAFT for unpublished tests)."""
    now = now or _now()
    if test.status == TestStatus.DRAFT:
        return "DRAFT"
    if test.status in (TestStatus.CLOSED, TestStatus.ARCHIVED) or test.ends_at <= now:
        return "CLOSED"
    if test.starts_at > now:
        return "UPCOMING"
    return "OPEN"


def _snapshot(test: Test) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in (*_TEST_FIELDS, "status"):
        value = getattr(test, field)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, uuid.UUID):
            value = str(value)
        result[field] = value
    return result


def _validate(test: Test) -> None:
    if test.ends_at <= test.starts_at:
        raise BadRequestError("INVALID_DATES", "Test yopilish vaqti ochilish vaqtidan keyin bo'lishi kerak.")
    if test.passing_score > test.max_score:
        raise BadRequestError("INVALID_PASSING_SCORE", "O'tish bali maksimal balldan katta bo'lishi mumkin emas.")


def scale(raw: int, raw_max: int, max_score: int) -> int:
    """round(raw / raw_max × max_score), halves rounded up, in integer arithmetic."""
    if raw_max <= 0:
        return 0
    return (2 * raw * max_score + raw_max) // (2 * raw_max)


def ledger_value(test: Test, score: int | None) -> int:
    """Points an attempt is worth in the ledger: nothing below the passing score."""
    if not score or score < test.passing_score:
        return 0
    return score


def passed(test: Test, score: int | None) -> bool:
    return ledger_value(test, score) > 0


# ---------------------------------------------------------------------------- shared lookups


async def get_test(session: AsyncSession, test_id: uuid.UUID) -> Test:
    test = await session.get(Test, test_id)
    if test is None or test.deleted_at is not None:
        raise NotFoundError("TEST_NOT_FOUND", "Test topilmadi.")
    return test


async def book_titles(session: AsyncSession, book_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not book_ids:
        return {}
    return dict((await session.execute(select(Book.id, Book.title).where(Book.id.in_(book_ids)))).all())


async def question_counts(session: AsyncSession, test_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not test_ids:
        return {}
    rows = await session.execute(
        select(TestQuestion.test_id, func.count())
        .where(TestQuestion.test_id.in_(test_ids))
        .group_by(TestQuestion.test_id)
    )
    return dict(rows.all())


async def participant_counts(session: AsyncSession, test_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not test_ids:
        return {}
    rows = await session.execute(
        select(TestAttempt.test_id, func.count(func.distinct(TestAttempt.user_id)))
        .where(TestAttempt.test_id.in_(test_ids))
        .group_by(TestAttempt.test_id)
    )
    return dict(rows.all())


async def load_questions(session: AsyncSession, test_id: uuid.UUID) -> list[tuple[TestQuestion, list[TestOption]]]:
    questions = list(
        await session.scalars(
            select(TestQuestion)
            .where(TestQuestion.test_id == test_id)
            .order_by(TestQuestion.sort_order, TestQuestion.created_at)
        )
    )
    options: dict[uuid.UUID, list[TestOption]] = defaultdict(list)
    if questions:
        for option in await session.scalars(
            select(TestOption)
            .where(TestOption.question_id.in_([q.id for q in questions]))
            .order_by(TestOption.sort_order)
        ):
            options[option.question_id].append(option)
    return [(question, options[question.id]) for question in questions]


async def _has_attempts(session: AsyncSession, test_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(select(func.count()).select_from(TestAttempt).where(TestAttempt.test_id == test_id))
    )


# ---------------------------------------------------------------------------- admin: editor


async def list_tests_admin(session: AsyncSession, *, limit: int, offset: int) -> tuple[list[Test], int]:
    conditions = [Test.deleted_at.is_(None)]
    total = await session.scalar(select(func.count()).select_from(Test).where(*conditions))
    rows = await session.scalars(
        select(Test).where(*conditions).order_by(Test.starts_at.desc()).limit(limit).offset(offset)
    )
    return list(rows), int(total or 0)


async def _ensure_book(session: AsyncSession, book_id: uuid.UUID) -> None:
    book = await session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        raise BadRequestError("BOOK_NOT_FOUND", "Tanlangan kitob topilmadi.")


async def create_test(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> Test:
    values = {key: value for key, value in data.items() if key in _TEST_FIELDS and value is not None}
    values.setdefault("max_score", await get_setting(session, "score.test_max_points"))
    if values.get("book_id"):
        await _ensure_book(session, values["book_id"])
    test = Test(**values, season_id=await current_season_id(session), created_by=actor_id, status=TestStatus.DRAFT)
    test.passing_score = values.get("passing_score", 0)
    _validate(test)
    session.add(test)
    await session.flush()
    record_audit(
        session, actor_id=actor_id, action="TEST_CREATE", entity_type="test", entity_id=test.id, after=_snapshot(test)
    )
    await session.commit()
    return test


async def update_test(
    session: AsyncSession, *, actor_id: uuid.UUID, test_id: uuid.UUID, changes: dict[str, Any]
) -> Test:
    test = await get_test(session, test_id)
    before = _snapshot(test)
    if changes.get("book_id"):
        await _ensure_book(session, changes["book_id"])
    locked = [f for f in _LOCKED_AFTER_ATTEMPTS if f in changes and changes[f] != getattr(test, f)]
    if locked and await _has_attempts(session, test.id):
        raise ConflictError(
            "TEST_HAS_ATTEMPTS",
            "Test boshlangan: maksimal ball va o'tish balini endi o'zgartirib bo'lmaydi.",
            details={"fields": locked},
        )
    for field, value in changes.items():
        if field in _TEST_FIELDS:
            setattr(test, field, value)
    _validate(test)
    after = _snapshot(test)
    if before != after:
        record_audit(
            session,
            actor_id=actor_id,
            action="TEST_UPDATE",
            entity_type="test",
            entity_id=test.id,
            before=before,
            after=after,
        )
    await session.commit()
    return test


async def replace_questions(
    session: AsyncSession, *, actor_id: uuid.UUID, test_id: uuid.UUID, questions: list[dict[str, Any]]
) -> Test:
    """Save the whole question list at once (the editor sends everything on "Save")."""
    test = await get_test(session, test_id)
    if await _has_attempts(session, test.id):
        raise ConflictError("TEST_HAS_ATTEMPTS", "A'zolar testni boshlagan — savollarni endi o'zgartirib bo'lmaydi.")
    before = await load_questions(session, test.id)
    before_count = len(before)
    old_images = {question.image_key for question, _ in before if question.image_key}
    own_prefix = f"tests/{test.id}/"
    kept_images: set[str] = set()
    await session.execute(delete(TestQuestion).where(TestQuestion.test_id == test.id))
    for index, item in enumerate(questions):
        image = item.get("image_key")
        if image and not str(image).startswith(own_prefix):
            raise BadRequestError("IMAGE_NOT_FOUND", f"{index + 1}-savol rasmi topilmadi. Rasmni qayta yuklang.")
        if image:
            kept_images.add(image)
        question = TestQuestion(
            test_id=test.id,
            type=item["type"],
            text=item["text"],
            points=item["points"],
            explanation=item.get("explanation"),
            sort_order=index,
            image_key=image or None,
        )
        session.add(question)
        await session.flush()
        for option_index, option in enumerate(item["options"]):
            session.add(
                TestOption(
                    question_id=question.id,
                    text=option["text"],
                    is_correct=option["is_correct"],
                    sort_order=option_index,
                )
            )
    record_audit(
        session,
        actor_id=actor_id,
        action="TEST_QUESTIONS_UPDATE",
        entity_type="test",
        entity_id=test.id,
        before={"questions": before_count},
        after={"questions": len(questions)},
    )
    await session.commit()
    storage = get_storage()
    for key in old_images - kept_images:  # pictures of removed questions
        try:
            await storage.delete(key)
        except Exception:  # an orphaned file is harmless
            logger.info("An old question picture could not be removed")
    return test


async def question_image(
    session: AsyncSession, *, user_id: uuid.UUID, test_id: uuid.UUID, question_id: uuid.UUID
) -> bytes:
    """A question's picture for a member who has started (or finished) this test."""
    test = await get_member_test(session, test_id)
    question = await session.get(TestQuestion, question_id)
    if question is None or question.test_id != test.id or not question.image_key:
        raise NotFoundError("IMAGE_NOT_FOUND", "Rasm topilmadi.")
    started = await session.scalar(
        select(TestAttempt.id).where(TestAttempt.test_id == test.id, TestAttempt.user_id == user_id).limit(1)
    )
    if started is None and state(test) != "CLOSED":
        raise ForbiddenError("TEST_NOT_STARTED", "Rasm test boshlanganda ko'rinadi.")
    return await get_storage().get(question.image_key)


def question_problems(question: TestQuestion, options: list[TestOption]) -> list[str]:
    problems = []
    correct = sum(1 for option in options if option.is_correct)
    if len(options) < 2:
        problems.append("kamida 2 ta variant kerak")
    if question.type == QuestionType.SINGLE_CHOICE and correct != 1:
        problems.append("bitta to'g'ri javob belgilanishi kerak")
    if question.type == QuestionType.MULTIPLE_CHOICE and correct < 1:
        problems.append("kamida bitta to'g'ri javob belgilanishi kerak")
    return problems


async def publish_test(session: AsyncSession, *, actor_id: uuid.UUID, test_id: uuid.UUID) -> Test:
    test = await get_test(session, test_id)
    if test.status != TestStatus.DRAFT:
        raise ConflictError("TEST_NOT_DRAFT", "Faqat qoralama testni e'lon qilish mumkin.")
    questions = await load_questions(session, test.id)
    if not questions:
        raise BadRequestError("TEST_HAS_NO_QUESTIONS", "E'lon qilishdan oldin savollar qo'shing.")
    problems = [
        {"question": index, "problems": issues}
        for index, (question, options) in enumerate(questions, start=1)
        if (issues := question_problems(question, options))
    ]
    if problems:
        raise BadRequestError("TEST_QUESTIONS_INVALID", "Ba'zi savollar to'liq emas.", details=problems)
    if test.ends_at <= _now():
        raise BadRequestError("TEST_ALREADY_ENDED", "Test yopilish vaqti o'tib ketgan. Vaqtni o'zgartiring.")
    test.status = TestStatus.PUBLISHED
    test.published_at = _now()
    test.published_by = actor_id
    record_audit(
        session,
        actor_id=actor_id,
        action="TEST_PUBLISH",
        entity_type="test",
        entity_id=test.id,
        after={"questions": len(questions)},
    )
    await session.commit()
    return test


async def unpublish_test(session: AsyncSession, *, actor_id: uuid.UUID, test_id: uuid.UUID) -> Test:
    test = await get_test(session, test_id)
    if test.status != TestStatus.PUBLISHED:
        raise ConflictError("TEST_NOT_PUBLISHED", "Test e'lon qilinmagan.")
    if await _has_attempts(session, test.id):
        raise ConflictError(
            "TEST_HAS_ATTEMPTS", "A'zolar testni boshlagan — uni qoralamaga qaytarib bo'lmaydi. Testni yoping."
        )
    test.status = TestStatus.DRAFT
    test.published_at = None
    record_audit(session, actor_id=actor_id, action="TEST_UNPUBLISH", entity_type="test", entity_id=test.id)
    await session.commit()
    return test


async def close_test(session: AsyncSession, *, actor_id: uuid.UUID | None, test_id: uuid.UUID) -> Test:
    """Close now (or after the end time): unfinished attempts are graded, place bonuses awarded."""
    test = await get_test(session, test_id)
    if test.status == TestStatus.DRAFT:
        raise ConflictError("TEST_NOT_PUBLISHED", "Test e'lon qilinmagan.")
    if test.status == TestStatus.PUBLISHED:
        now = _now()
        test.status = TestStatus.CLOSED
        if test.ends_at > now:
            test.ends_at = max(now, test.starts_at + timedelta(seconds=1))
        record_audit(session, actor_id=actor_id, action="TEST_CLOSE", entity_type="test", entity_id=test.id)
    await finalize_overdue_attempts(session, test_id=test.id, force=True)
    first_close = test.rank_bonus_awarded_at is None
    await award_rank_bonuses(session, test)
    if first_close:
        rows = await standings_with_attendance(session, test)
        await announcements.test_results(session, test, rows)
        await certificate_service.issue_for_test(session, test, await test_standings(session, test))
    await session.commit()
    return test


async def close_ended_tests(session: AsyncSession) -> int:
    """Scheduler job: close published tests whose end time has passed. Returns how many."""
    ids = list(
        await session.scalars(
            select(Test.id).where(
                Test.deleted_at.is_(None), Test.status == TestStatus.PUBLISHED, Test.ends_at <= _now()
            )
        )
    )
    pending_bonus = list(
        await session.scalars(
            select(Test.id).where(
                Test.deleted_at.is_(None), Test.status == TestStatus.CLOSED, Test.rank_bonus_awarded_at.is_(None)
            )
        )
    )
    for test_id in [*ids, *pending_bonus]:
        await close_test(session, actor_id=None, test_id=test_id)
    return len(ids)


async def delete_test(session: AsyncSession, *, actor_id: uuid.UUID, test_id: uuid.UUID) -> None:
    test = await get_test(session, test_id)
    if await _has_attempts(session, test.id):
        raise ConflictError(
            "TEST_HAS_ATTEMPTS", "Natijalari bor testni o'chirib bo'lmaydi — natijalar va ballar saqlanishi kerak."
        )
    test.deleted_at = _now()
    record_audit(
        session, actor_id=actor_id, action="TEST_DELETE", entity_type="test", entity_id=test.id, before=_snapshot(test)
    )
    await session.commit()


# ---------------------------------------------------------------------------- grading


async def _answer_key(session: AsyncSession, test_id: uuid.UUID) -> dict[uuid.UUID, tuple[int, frozenset[uuid.UUID]]]:
    """{question_id: (points, correct option ids)}"""
    rows = await session.execute(
        select(TestQuestion.id, TestQuestion.points, TestOption.id, TestOption.is_correct)
        .join(TestOption, TestOption.question_id == TestQuestion.id)
        .where(TestQuestion.test_id == test_id)
    )
    points: dict[uuid.UUID, int] = {}
    correct: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for question_id, question_points, option_id, is_correct in rows:
        points[question_id] = question_points
        if is_correct:
            correct[question_id].add(option_id)
    return {question_id: (points[question_id], frozenset(correct[question_id])) for question_id in points}


@dataclass(frozen=True)
class GradeResult:
    attempt: TestAttempt
    points_awarded: int


async def _grade(session: AsyncSession, test: Test, attempt: TestAttempt, status: AttemptStatus) -> GradeResult:
    """Grade the saved answers, finish the attempt and write ledger points. The caller commits."""
    key = await _answer_key(session, test.id)
    answers = {
        answer.question_id: answer
        for answer in await session.scalars(select(TestAnswer).where(TestAnswer.attempt_id == attempt.id))
    }
    raw = raw_max = correct_count = 0
    for question_id in attempt.question_order:
        if question_id not in key:
            continue
        question_points, correct_options = key[question_id]
        raw_max += question_points
        answer = answers.get(question_id)
        if answer is None:
            continue
        is_correct = bool(answer.selected_option_ids) and frozenset(answer.selected_option_ids) == correct_options
        answer.is_correct = is_correct
        answer.points_awarded = question_points if is_correct else 0
        if is_correct:
            raw += question_points
            correct_count += 1
    attempt.status = status
    attempt.submitted_at = _now()
    attempt.raw_score = raw
    attempt.raw_max = raw_max
    attempt.correct_count = correct_count
    attempt.score = scale(raw, raw_max, test.max_score)
    await session.flush()
    awarded = await _award_best_attempt_delta(session, test, attempt)
    if test.book_id and passed(test, attempt.score):
        await _verify_book(session, test, attempt.user_id)
        await session.flush()
    await achievements.evaluate(session, attempt.user_id)
    return GradeResult(attempt=attempt, points_awarded=awarded)


async def _award_best_attempt_delta(session: AsyncSession, test: Test, attempt: TestAttempt) -> int:
    previous_scores = await session.scalars(
        select(TestAttempt.score).where(
            TestAttempt.test_id == test.id,
            TestAttempt.user_id == attempt.user_id,
            TestAttempt.id != attempt.id,
            TestAttempt.status.in_(FINISHED),
        )
    )
    previous_best = max((ledger_value(test, score) for score in previous_scores), default=0)
    delta = ledger_value(test, attempt.score) - previous_best
    if delta <= 0:
        return 0
    created = await award_points(
        session,
        user_id=attempt.user_id,
        amount=delta,
        category=ScoreCategory.TEST,
        idempotency_key=f"test:{test.id}:attempt:{attempt.id}",
        source_type="TEST",
        source_id=test.id,
    )
    return delta if created else 0


async def _verify_book(session: AsyncSession, test: Test, user_id: uuid.UUID) -> None:
    assert test.book_id is not None
    read = await get_or_create_read(session, test.book_id, user_id)
    now = _now()
    if read.status != ReadingStatus.COMPLETED:
        read.status = ReadingStatus.COMPLETED
        read.completed_at = now
    if read.verified_at is None:
        read.verified_at = now
        read.verification_source = ReadingVerification.TEST
    await award_book_completion(session, read, None)


async def finalize_overdue_attempts(
    session: AsyncSession, *, test_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None, force: bool = False
) -> int:
    """Grade unfinished attempts whose time is up (``force``: all unfinished, e.g. on close).

    Answers saved before the deadline still count. The caller commits.
    """
    conditions = [TestAttempt.status == AttemptStatus.IN_PROGRESS]
    if not force:
        conditions.append(TestAttempt.deadline_at < _now() - NETWORK_GRACE)
    if test_id is not None:
        conditions.append(TestAttempt.test_id == test_id)
    if user_id is not None:
        conditions.append(TestAttempt.user_id == user_id)
    attempts = list(await session.scalars(select(TestAttempt).where(*conditions).with_for_update(skip_locked=True)))
    for attempt in attempts:
        test = await session.get(Test, attempt.test_id)
        assert test is not None
        session.add(
            TestActivityLog(attempt_id=attempt.id, user_id=attempt.user_id, event_type=TestActivityType.TIMEOUT)
        )
        await _grade(session, test, attempt, AttemptStatus.EXPIRED)
    return len(attempts)


async def award_rank_bonuses(session: AsyncSession, test: Test) -> int:
    """1st/2nd/3rd place bonuses once a test has closed. Runs once per test. The caller commits."""
    if test.rank_bonus_awarded_at is not None:
        return 0
    bonuses: list[int] = await get_setting(session, "score.test_rank_bonus")
    standings = await official_places(session, test, limit=len(bonuses))  # an event's test: attendees only
    awarded = 0
    for place, row in enumerate(standings, start=1):
        amount = bonuses[place - 1]
        if amount <= 0:
            continue
        created = await award_points(
            session,
            user_id=row["user_id"],
            amount=amount,
            category=ScoreCategory.TEST_RANK_BONUS,
            idempotency_key=f"test:{test.id}:rank-bonus:{row['user_id']}",
            source_type="TEST",
            source_id=test.id,
            reason=f"{place}-o'rin",
        )
        awarded += 1 if created else 0
    test.rank_bonus_awarded_at = _now()
    return awarded


async def test_standings(session: AsyncSession, test: Test) -> list[dict[str, Any]]:
    """Members ranked by their best passing attempt.

    Ties: higher score, then shorter solving time, then earlier finish, then member id.
    """
    rows = await session.execute(
        select(TestAttempt)
        .join(User, User.id == TestAttempt.user_id)
        .where(
            TestAttempt.test_id == test.id,
            TestAttempt.status.in_(FINISHED),
            TestAttempt.score > 0,
            TestAttempt.score >= test.passing_score,
            User.deleted_at.is_(None),
        )
    )
    best: dict[uuid.UUID, tuple[Any, ...]] = {}
    for (attempt,) in rows:
        assert attempt.submitted_at is not None and attempt.score is not None
        duration = (min(attempt.submitted_at, attempt.deadline_at) - attempt.started_at).total_seconds()
        sort_key = (-attempt.score, duration, attempt.submitted_at, str(attempt.user_id))
        if attempt.user_id not in best or sort_key < best[attempt.user_id]:
            best[attempt.user_id] = sort_key
    ordered = sorted(best.items(), key=lambda item: item[1])
    return [
        {"place": place, "user_id": user_id, "score": -key[0], "duration_seconds": int(key[1])}
        for place, (user_id, key) in enumerate(ordered, start=1)
    ]


async def _present(session: AsyncSession, test: Test) -> set[uuid.UUID] | None:
    """Members whose attendance at the test's event was confirmed (None: the test has no event)."""
    if test.event_id is None:
        return None
    return set(
        await session.scalars(
            select(AttendanceRecord.user_id).where(
                AttendanceRecord.event_id == test.event_id, AttendanceRecord.status == AttendanceStatus.VERIFIED
            )
        )
    )


async def standings_with_attendance(session: AsyncSession, test: Test) -> list[dict[str, Any]]:
    """Everybody in order of their result. For a test of an event, ``attended`` says whether the member
    was at the event, and only those who were take the prize places (``official_place``)."""
    standings = await test_standings(session, test)
    present = await _present(session, test)
    rows = []
    official = 0
    for row in standings:
        attended = None if present is None else row["user_id"] in present
        official_place = None
        if attended is not False:
            official += 1
            official_place = official
        rows.append({**row, "attended": attended, "official_place": official_place})
    return rows


async def official_places(session: AsyncSession, test: Test, limit: int = 3) -> list[dict[str, Any]]:
    """Places 1..limit as announced: for a test of an event only members whose attendance at
    that event was confirmed take places (the same rule as for certificates and prizes)."""
    rows = await standings_with_attendance(session, test)
    return [
        {
            "place": row["official_place"],
            "user_id": row["user_id"],
            "score": row["score"],
            "duration_seconds": row["duration_seconds"],
        }
        for row in rows
        if row["official_place"] is not None and row["official_place"] <= limit
    ]


async def public_standings(
    session: AsyncSession, *, user_id: uuid.UUID, test_id: uuid.UUID, limit: int = 20
) -> dict[str, Any]:
    """The closed test's table for members: names as in the club ranking, «davomatsiz» marks."""
    from app.services.ranking import display_name

    test = await get_member_test(session, test_id)
    if state(test) != "CLOSED":
        raise ForbiddenError("STANDINGS_NOT_AVAILABLE", "O'rinlar test yopilgandan keyin e'lon qilinadi.")
    rows = await standings_with_attendance(session, test)
    shown = rows[:limit]
    mine = next((row for row in rows if row["user_id"] == user_id), None)
    if mine is not None and mine not in shown:
        shown = [*shown, mine]
    name_format = str(await get_setting(session, "ranking.public_name_format"))
    users = {
        user.id: user
        for user in await session.scalars(select(User).where(User.id.in_([row["user_id"] for row in shown])))
    }
    return {
        "test_id": test.id,
        "title": test.title,
        "max_score": test.max_score,
        "event_test": test.event_id is not None,
        "participants": len(rows),
        "rows": [
            {
                "place": row["place"],
                "prize_place": row["official_place"] if row["official_place"] and row["official_place"] <= 3 else None,
                "name": display_name(
                    users[row["user_id"]].first_name, users[row["user_id"]].last_name or "", name_format
                )
                if row["user_id"] in users
                else "—",
                "score": row["score"],
                "attended": row["attended"],
                "me": row["user_id"] == user_id,
            }
            for row in shown
        ],
    }


# ---------------------------------------------------------------------------- members


async def get_member_test(session: AsyncSession, test_id: uuid.UUID) -> Test:
    test = await get_test(session, test_id)
    if test.status not in MEMBER_VISIBLE:
        raise NotFoundError("TEST_NOT_FOUND", "Test topilmadi.")
    return test


async def list_member_tests(session: AsyncSession, *, user_id: uuid.UUID) -> list[Test]:
    await finalize_overdue_attempts(session, user_id=user_id)
    await session.commit()
    tests = list(
        await session.scalars(
            select(Test)
            .where(Test.deleted_at.is_(None), Test.status.in_(MEMBER_VISIBLE))
            .order_by(Test.starts_at.desc())
        )
    )
    now = _now()
    order = {"OPEN": 0, "UPCOMING": 1, "CLOSED": 2}
    # Open tests first (closing soonest first), then upcoming (soonest first), then closed (newest first).
    return sorted(
        tests,
        key=lambda t: (
            order[state(t, now)],
            t.ends_at.timestamp() if state(t, now) == "OPEN" else 0,
            t.starts_at.timestamp() if state(t, now) == "UPCOMING" else -t.ends_at.timestamp(),
        ),
    )


async def my_attempts(
    session: AsyncSession, *, user_id: uuid.UUID, test_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[TestAttempt]]:
    result: dict[uuid.UUID, list[TestAttempt]] = defaultdict(list)
    if test_ids:
        for attempt in await session.scalars(
            select(TestAttempt)
            .where(TestAttempt.user_id == user_id, TestAttempt.test_id.in_(test_ids))
            .order_by(TestAttempt.attempt_number)
        ):
            result[attempt.test_id].append(attempt)
    return result


async def _in_progress(
    session: AsyncSession, *, user_id: uuid.UUID, test_id: uuid.UUID, lock: bool = False
) -> TestAttempt | None:
    statement = select(TestAttempt).where(
        TestAttempt.user_id == user_id,
        TestAttempt.test_id == test_id,
        TestAttempt.status == AttemptStatus.IN_PROGRESS,
    )
    if lock:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def start_attempt(session: AsyncSession, *, user: User, test_id: uuid.UUID) -> tuple[Test, TestAttempt]:
    """Start (or resume) an attempt. The server fixes the start time, deadline and order."""
    test = await get_member_test(session, test_id)
    await finalize_overdue_attempts(session, test_id=test.id, user_id=user.id)
    await session.commit()
    existing = await _in_progress(session, user_id=user.id, test_id=test.id)
    if existing is not None:
        session.add(TestActivityLog(attempt_id=existing.id, user_id=user.id, event_type=TestActivityType.RECONNECTED))
        await session.commit()
        return test, existing

    now = _now()
    current_state = state(test, now)
    if current_state == "UPCOMING":
        raise ConflictError("TEST_NOT_STARTED", "Test hali boshlanmagan.")
    if current_state == "CLOSED":
        raise ConflictError("TEST_CLOSED", "Test yopilgan.")
    used = await session.scalar(
        select(func.count())
        .select_from(TestAttempt)
        .where(TestAttempt.test_id == test.id, TestAttempt.user_id == user.id)
    )
    if used >= test.attempts_allowed:
        raise ConflictError("NO_ATTEMPTS_LEFT", "Bu test uchun urinishlaringiz tugagan.")
    questions = await load_questions(session, test.id)
    if not questions:
        raise ConflictError("TEST_HAS_NO_QUESTIONS", "Testda savollar yo'q.")

    question_ids = [question.id for question, _ in questions]
    if test.shuffle_questions:
        _random.shuffle(question_ids)
    option_order: dict[str, list[str]] = {}
    for question, options in questions:
        ids = [str(option.id) for option in options]
        if test.shuffle_options:
            _random.shuffle(ids)
        option_order[str(question.id)] = ids

    attempt = TestAttempt(
        test_id=test.id,
        user_id=user.id,
        attempt_number=int(used) + 1,
        status=AttemptStatus.IN_PROGRESS,
        started_at=now,
        deadline_at=min(now + timedelta(minutes=test.duration_minutes), test.ends_at),
        question_order=question_ids,
        option_order=option_order,
    )
    try:
        async with session.begin_nested():
            session.add(attempt)
    except IntegrityError:
        # A parallel request (double tap) started the attempt first: resume that one.
        existing = await _in_progress(session, user_id=user.id, test_id=test.id)
        if existing is None:
            raise ConflictError("ATTEMPT_CONFLICT", "Iltimos, qayta urinib ko'ring.") from None
        return test, existing
    await session.commit()
    return test, attempt


async def current_attempt(session: AsyncSession, *, user_id: uuid.UUID, test_id: uuid.UUID) -> tuple[Test, TestAttempt]:
    test = await get_member_test(session, test_id)
    await finalize_overdue_attempts(session, test_id=test.id, user_id=user_id)
    await session.commit()
    attempt = await _in_progress(session, user_id=user_id, test_id=test.id)
    if attempt is None:
        raise NotFoundError("NO_ACTIVE_ATTEMPT", "Faol urinish yo'q.")
    return test, attempt


async def attempt_questions(
    session: AsyncSession, attempt: TestAttempt
) -> tuple[list[tuple[TestQuestion, list[TestOption]]], dict[uuid.UUID, list[uuid.UUID]]]:
    """Questions and options in this attempt's order (without correct flags), and saved answers."""
    loaded = {question.id: (question, options) for question, options in await load_questions(session, attempt.test_id)}
    ordered = []
    for question_id in attempt.question_order:
        if question_id not in loaded:
            continue
        question, options = loaded[question_id]
        by_id = {str(option.id): option for option in options}
        order = attempt.option_order.get(str(question_id), list(by_id))
        ordered.append((question, [by_id[option_id] for option_id in order if option_id in by_id]))
    answers = {
        answer.question_id: list(answer.selected_option_ids)
        for answer in await session.scalars(select(TestAnswer).where(TestAnswer.attempt_id == attempt.id))
    }
    return ordered, answers


async def _expire_and_raise(session: AsyncSession, test: Test, attempt: TestAttempt) -> None:
    session.add(TestActivityLog(attempt_id=attempt.id, user_id=attempt.user_id, event_type=TestActivityType.TIMEOUT))
    await _grade(session, test, attempt, AttemptStatus.EXPIRED)
    await session.commit()
    raise ConflictError("TEST_TIME_EXPIRED", "Vaqt tugadi. Vaqt ichida belgilangan javoblaringiz hisobga olindi.")


async def _save_answer(
    session: AsyncSession, attempt: TestAttempt, question_id: uuid.UUID, option_ids: list[uuid.UUID]
) -> None:
    if question_id not in attempt.question_order:
        raise BadRequestError("QUESTION_NOT_IN_TEST", "Savol bu testga tegishli emas.")
    question = await session.get(TestQuestion, question_id)
    assert question is not None
    allowed = {uuid.UUID(option_id) for option_id in attempt.option_order.get(str(question_id), [])}
    selected = list(dict.fromkeys(option_ids))
    if any(option_id not in allowed for option_id in selected):
        raise BadRequestError("OPTION_NOT_IN_QUESTION", "Tanlangan javob bu savolga tegishli emas.")
    if question.type == QuestionType.SINGLE_CHOICE and len(selected) > 1:
        raise BadRequestError("SINGLE_CHOICE_ONLY", "Bu savolda faqat bitta javob tanlanadi.")
    statement = insert(TestAnswer).values(attempt_id=attempt.id, question_id=question_id, selected_option_ids=selected)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[TestAnswer.attempt_id, TestAnswer.question_id],
            set_={"selected_option_ids": statement.excluded.selected_option_ids, "updated_at": func.now()},
        )
    )


async def save_answer(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    test_id: uuid.UUID,
    question_id: uuid.UUID,
    option_ids: list[uuid.UUID],
) -> None:
    test = await get_member_test(session, test_id)
    attempt = await _in_progress(session, user_id=user_id, test_id=test.id, lock=True)
    if attempt is None:
        raise ConflictError("NO_ACTIVE_ATTEMPT", "Faol urinish yo'q. Testni qaytadan oching.")
    if _now() > attempt.deadline_at + NETWORK_GRACE:
        await _expire_and_raise(session, test, attempt)
    await _save_answer(session, attempt, question_id, option_ids)
    await session.commit()


async def submit_attempt(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    test_id: uuid.UUID,
    answers: list[tuple[uuid.UUID, list[uuid.UUID]]] | None,
) -> GradeResult:
    """Finish the attempt. Repeating the request returns the same result (idempotent)."""
    test = await get_member_test(session, test_id)
    attempt = await _in_progress(session, user_id=user_id, test_id=test.id, lock=True)
    if attempt is None:
        latest = await session.scalar(
            select(TestAttempt)
            .where(TestAttempt.user_id == user_id, TestAttempt.test_id == test.id, TestAttempt.status.in_(FINISHED))
            .order_by(TestAttempt.attempt_number.desc())
        )
        if latest is None:
            raise ConflictError("NO_ACTIVE_ATTEMPT", "Faol urinish yo'q.")
        return GradeResult(attempt=latest, points_awarded=await points_for_attempt(session, latest))
    if _now() > attempt.deadline_at + NETWORK_GRACE:
        await _expire_and_raise(session, test, attempt)
    for question_id, option_ids in answers or []:
        await _save_answer(session, attempt, question_id, option_ids)
    await session.flush()
    answered = await session.scalar(
        select(func.count())
        .select_from(TestAnswer)
        .where(TestAnswer.attempt_id == attempt.id, func.cardinality(TestAnswer.selected_option_ids) > 0)
    )
    elapsed = (_now() - attempt.started_at).total_seconds()
    if answered and answered >= 3 and elapsed / answered < FAST_ANSWER_SECONDS:
        session.add(
            TestActivityLog(
                attempt_id=attempt.id,
                user_id=user_id,
                event_type=TestActivityType.FAST_ANSWER,
                details={"answered": int(answered), "seconds": round(elapsed, 1)},
            )
        )
    result = await _grade(session, test, attempt, AttemptStatus.SUBMITTED)
    await session.commit()
    return result


async def points_for_attempt(session: AsyncSession, attempt: TestAttempt) -> int:
    amount = await session.scalar(
        select(ScoreTransaction.amount).where(
            ScoreTransaction.idempotency_key == f"test:{attempt.test_id}:attempt:{attempt.id}"
        )
    )
    return int(amount or 0)


async def log_activity(
    session: AsyncSession, *, user_id: uuid.UUID, test_id: uuid.UUID, events: list[dict[str, Any]]
) -> int:
    """Store focus/visibility signals for the running attempt. Signals are hints, never proof."""
    attempt = await _in_progress(session, user_id=user_id, test_id=test_id)
    if attempt is None:
        return 0
    for item in events:
        session.add(
            TestActivityLog(
                attempt_id=attempt.id,
                user_id=user_id,
                event_type=item["type"],
                client_time=item.get("client_time"),
                details=item.get("details"),
            )
        )
    await session.commit()
    return len(events)


async def review(session: AsyncSession, *, user_id: uuid.UUID, test_id: uuid.UUID) -> dict[str, Any]:
    """Correct answers and explanations — only after the test has closed, for the best attempt."""
    test = await get_member_test(session, test_id)
    if state(test) != "CLOSED":
        raise ForbiddenError("REVIEW_NOT_AVAILABLE", "To'g'ri javoblar test yopilgandan keyin ko'rinadi.")
    attempts = (await my_attempts(session, user_id=user_id, test_ids=[test.id]))[test.id]
    finished = [a for a in attempts if a.status in FINISHED]
    if not finished:
        raise NotFoundError("NO_ATTEMPT", "Siz bu testda qatnashmagansiz.")
    best = sorted(finished, key=lambda a: (-(a.score or 0), a.attempt_number))[0]
    ordered, _ = await attempt_questions(session, best)
    answers = {
        answer.question_id: answer
        for answer in await session.scalars(select(TestAnswer).where(TestAnswer.attempt_id == best.id))
    }
    questions = []
    for question, options in ordered:
        answer = answers.get(question.id)
        selected = set(answer.selected_option_ids) if answer else set()
        questions.append(
            {
                "id": question.id,
                "type": question.type,
                "text": question.text,
                "points": question.points,
                "explanation": question.explanation,
                "is_correct": bool(answer and answer.is_correct),
                "points_awarded": (answer.points_awarded or 0) if answer else 0,
                "has_image": question.image_key is not None,
                "options": [
                    {"id": o.id, "text": o.text, "is_correct": o.is_correct, "selected": o.id in selected}
                    for o in options
                ],
            }
        )
    standings = await standings_with_attendance(session, test)
    mine = next((row for row in standings if row["user_id"] == user_id), None)
    place = mine["place"] if mine else None
    return {
        "test_id": test.id,
        "title": test.title,
        "score": best.score or 0,
        "max_score": test.max_score,
        "correct_count": best.correct_count or 0,
        "question_count": len(questions),
        "place": place,
        "attended": mine["attended"] if mine else None,
        "participants": len(standings),
        "questions": questions,
    }


# ---------------------------------------------------------------------------- admin: results


async def results(session: AsyncSession, test_id: uuid.UUID) -> tuple[Test, list[dict[str, Any]]]:
    test = await get_test(session, test_id)
    if await finalize_overdue_attempts(session, test_id=test.id):
        await session.commit()
    rows = await session.execute(
        select(TestAttempt, User, Faculty.name)
        .join(User, User.id == TestAttempt.user_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .where(TestAttempt.test_id == test.id)
        .order_by(TestAttempt.score.desc().nulls_last(), TestAttempt.submitted_at)
    )
    attempts = [(attempt, user, faculty) for attempt, user, faculty in rows]
    signals = dict(
        (
            await session.execute(
                select(TestActivityLog.attempt_id, func.count())
                .where(
                    TestActivityLog.attempt_id.in_([a.id for a, _, _ in attempts]),
                    TestActivityLog.event_type.not_in(NEUTRAL_SIGNALS),
                    TestActivityLog.event_type != TestActivityType.RECONNECTED,
                )
                .group_by(TestActivityLog.attempt_id)
            )
        ).all()
    )
    table = {row["user_id"]: row for row in await standings_with_attendance(session, test)}
    places = {user_id: row["place"] for user_id, row in table.items()}
    items = []
    for attempt, user, faculty in attempts:
        finished_at = attempt.submitted_at
        items.append(
            {
                "attempt_id": attempt.id,
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "faculty": faculty,
                "course": user.course,
                "group_name": user.group_name,
                "attempt_number": attempt.attempt_number,
                "status": attempt.status,
                "score": attempt.score,
                "correct_count": attempt.correct_count,
                "question_count": len(attempt.question_order),
                "passed": passed(test, attempt.score) if attempt.status in FINISHED else None,
                "started_at": attempt.started_at,
                "submitted_at": finished_at,
                "duration_seconds": int((min(finished_at, attempt.deadline_at) - attempt.started_at).total_seconds())
                if finished_at
                else None,
                "signals": int(signals.get(attempt.id, 0)),
                "place": places.get(user.id),
                "attended": table[user.id]["attended"] if user.id in table else None,
                "prize_place": table[user.id]["official_place"] if user.id in table else None,
            }
        )
    return test, items


async def attempt_detail(session: AsyncSession, attempt_id: uuid.UUID) -> dict[str, Any]:
    attempt = await session.get(TestAttempt, attempt_id)
    if attempt is None:
        raise NotFoundError("ATTEMPT_NOT_FOUND", "Urinish topilmadi.")
    user = await session.get(User, attempt.user_id)
    assert user is not None
    ordered, _ = await attempt_questions(session, attempt)
    answers = {
        answer.question_id: answer
        for answer in await session.scalars(select(TestAnswer).where(TestAnswer.attempt_id == attempt.id))
    }
    logs = list(
        await session.scalars(
            select(TestActivityLog).where(TestActivityLog.attempt_id == attempt.id).order_by(TestActivityLog.created_at)
        )
    )
    return {
        "attempt_id": attempt.id,
        "member": f"{user.first_name} {user.last_name}",
        "status": attempt.status,
        "score": attempt.score,
        "started_at": attempt.started_at,
        "deadline_at": attempt.deadline_at,
        "submitted_at": attempt.submitted_at,
        "answers": [
            {
                "question": question.text,
                "selected": [
                    o.text
                    for o in options
                    if answers.get(question.id) and o.id in answers[question.id].selected_option_ids
                ],
                "correct": [o.text for o in options if o.is_correct],
                "is_correct": answers[question.id].is_correct if question.id in answers else False,
                "answered_at": answers[question.id].updated_at if question.id in answers else None,
            }
            for question, options in ordered
        ],
        "activity": [{"type": log.event_type, "at": log.created_at, "details": log.details} for log in logs],
    }


_STATUS_LABELS = {
    AttemptStatus.SUBMITTED: "Topshirildi",
    AttemptStatus.EXPIRED: "Vaqt tugadi",
    AttemptStatus.IN_PROGRESS: "Yechilmoqda",
}


async def export_csv(session: AsyncSession, test_id: uuid.UUID) -> tuple[str, str]:
    """(file name, CSV text with BOM so that Excel opens Uzbek letters correctly)."""
    test, items = await results(session, test_id)
    buffer = io.StringIO()
    writer = excel_writer(buffer)
    writer.writerow(
        [
            "O'rin",
            "Familiya",
            "Ism",
            "Fakultet",
            "Kurs",
            "Guruh",
            "Urinish",
            "Holat",
            "To'g'ri",
            "Ball",
            "O'tdi",
            "Sarflangan vaqt (daq.)",
            "Signallar",
            "Tugatgan vaqti",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item["place"] or "",
                item["last_name"],
                item["first_name"],
                item["faculty"] or "",
                item["course"] or "",
                item["group_name"] or "",
                item["attempt_number"],
                _STATUS_LABELS[item["status"]],
                f"{item['correct_count'] or 0}/{item['question_count']}",
                item["score"] if item["score"] is not None else "",
                {True: "ha", False: "yo'q", None: ""}[item["passed"]],
                round(item["duration_seconds"] / 60, 1) if item["duration_seconds"] is not None else "",
                item["signals"],
                format_datetime(item["submitted_at"]),
            ]
        )
    safe_title = "".join(ch if ch.isalnum() else "_" for ch in test.title)[:40] or "test"
    return f"test_{safe_title}.csv", "﻿" + buffer.getvalue()
