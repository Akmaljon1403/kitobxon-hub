"""Knowledge tests for members: list, start, answer, submit, activity signals and review."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, CurrentUserDep, DbSession, get_current_user
from app.models import Test, TestAttempt
from app.schemas.quiz import (
    ActivityIn,
    AnswerIn,
    AnswerSavedOut,
    AttemptOut,
    AttemptResultOut,
    MyAttemptOut,
    OptionOut,
    QuestionOut,
    ReviewOut,
    SubmitIn,
    TestOut,
)
from app.security.rate_limit import RateLimit, enforce
from app.services import quizzes as quiz_service

router = APIRouter(tags=["tests"])
ANSWER_LIMIT = RateLimit("test-answer", limit=120, window_seconds=60)
ACTIVITY_LIMIT = RateLimit("test-activity", limit=30, window_seconds=60)


async def _answer_rate_limit(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    await enforce(ANSWER_LIMIT, str(current.user.id))
    return current


async def _activity_rate_limit(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    await enforce(ACTIVITY_LIMIT, str(current.user.id))
    return current


def _test_out(test: Test, attempts: list[TestAttempt], question_count: int, book_title: str | None) -> TestOut:
    current_state = quiz_service.state(test)
    finished = [a for a in attempts if a.status in quiz_service.FINISHED]
    in_progress = any(a.status not in quiz_service.FINISHED for a in attempts)
    return TestOut(
        id=test.id,
        title=test.title,
        description=test.description,
        book_id=test.book_id,
        book_title=book_title,
        starts_at=test.starts_at,
        ends_at=test.ends_at,
        duration_minutes=test.duration_minutes,
        max_score=test.max_score,
        passing_score=test.passing_score,
        attempts_allowed=test.attempts_allowed,
        question_count=question_count,
        state=current_state,
        attempts=[
            MyAttemptOut(
                attempt_number=a.attempt_number,
                status=a.status,
                score=a.score,
                correct_count=a.correct_count,
                question_count=len(a.question_order),
                submitted_at=a.submitted_at,
            )
            for a in attempts
        ],
        best_score=max((a.score or 0 for a in finished), default=None),
        in_progress=in_progress,
        can_start=current_state == "OPEN" and (in_progress or len(attempts) < test.attempts_allowed),
        review_available=current_state == "CLOSED" and bool(finished),
    )


async def _tests_out(db, user_id: uuid.UUID, tests: list[Test]) -> list[TestOut]:
    ids = [test.id for test in tests]
    attempts = await quiz_service.my_attempts(db, user_id=user_id, test_ids=ids)
    counts = await quiz_service.question_counts(db, ids)
    titles = await quiz_service.book_titles(db, {test.book_id for test in tests if test.book_id})
    return [
        _test_out(
            test, attempts.get(test.id, []), counts.get(test.id, 0), titles.get(test.book_id) if test.book_id else None
        )
        for test in tests
    ]


async def _attempt_out(db, test: Test, attempt: TestAttempt) -> AttemptOut:
    questions, answers = await quiz_service.attempt_questions(db, attempt)
    return AttemptOut(
        attempt_id=attempt.id,
        test_id=test.id,
        title=test.title,
        attempt_number=attempt.attempt_number,
        started_at=attempt.started_at,
        deadline_at=attempt.deadline_at,
        server_now=datetime.now(UTC),
        questions=[
            QuestionOut(
                id=question.id,
                type=question.type,
                text=question.text,
                points=question.points,
                options=[OptionOut(id=option.id, text=option.text) for option in options],
            )
            for question, options in questions
        ],
        answers=answers,
    )


@router.get("/tests", response_model=list[TestOut], summary="Tests: open, upcoming and closed")
async def list_tests(current: CurrentUserDep, db: DbSession) -> list[TestOut]:
    tests = await quiz_service.list_member_tests(db, user_id=current.user.id)
    return await _tests_out(db, current.user.id, tests)


@router.get("/tests/{test_id}", response_model=TestOut, summary="One test with my attempts")
async def get_test(test_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> TestOut:
    test = await quiz_service.get_member_test(db, test_id)
    await quiz_service.finalize_overdue_attempts(db, test_id=test.id, user_id=current.user.id)
    await db.commit()
    return (await _tests_out(db, current.user.id, [test]))[0]


@router.post("/tests/{test_id}/start", response_model=AttemptOut, summary="Start or resume my attempt")
async def start(test_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> AttemptOut:
    test, attempt = await quiz_service.start_attempt(db, user=current.user, test_id=test_id)
    return await _attempt_out(db, test, attempt)


@router.get("/tests/{test_id}/attempt", response_model=AttemptOut, summary="My running attempt")
async def running_attempt(test_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> AttemptOut:
    test, attempt = await quiz_service.current_attempt(db, user_id=current.user.id, test_id=test_id)
    return await _attempt_out(db, test, attempt)


@router.post("/tests/{test_id}/answer", response_model=AnswerSavedOut, summary="Save one answer")
async def answer(
    test_id: uuid.UUID, payload: AnswerIn, current: Annotated[CurrentUser, Depends(_answer_rate_limit)], db: DbSession
) -> AnswerSavedOut:
    await quiz_service.save_answer(
        db, user_id=current.user.id, test_id=test_id, question_id=payload.question_id, option_ids=payload.option_ids
    )
    return AnswerSavedOut(server_now=datetime.now(UTC))


@router.post(
    "/tests/{test_id}/submit", response_model=AttemptResultOut, summary="Finish the attempt (server grades it)"
)
async def submit(
    test_id: uuid.UUID, payload: SubmitIn, current: Annotated[CurrentUser, Depends(_answer_rate_limit)], db: DbSession
) -> AttemptResultOut:
    answers = [(item.question_id, item.option_ids) for item in payload.answers] if payload.answers else None
    result = await quiz_service.submit_attempt(db, user_id=current.user.id, test_id=test_id, answers=answers)
    test = await quiz_service.get_test(db, test_id)
    attempt = result.attempt
    used = len((await quiz_service.my_attempts(db, user_id=current.user.id, test_ids=[test.id]))[test.id])
    return AttemptResultOut(
        attempt_id=attempt.id,
        status=attempt.status,
        score=attempt.score or 0,
        max_score=test.max_score,
        passing_score=test.passing_score,
        passed=quiz_service.passed(test, attempt.score),
        correct_count=attempt.correct_count or 0,
        question_count=len(attempt.question_order),
        points_awarded=result.points_awarded,
        submitted_at=attempt.submitted_at,
        attempts_left=max(0, test.attempts_allowed - used),
        review_available_at=test.ends_at,
    )


@router.post(
    "/tests/{test_id}/activity",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Focus/visibility signals during an attempt (hints, not proof)",
)
async def activity(
    test_id: uuid.UUID,
    payload: ActivityIn,
    current: Annotated[CurrentUser, Depends(_activity_rate_limit)],
    db: DbSession,
) -> Response:
    await quiz_service.log_activity(
        db, user_id=current.user.id, test_id=test_id, events=[item.model_dump() for item in payload.events]
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tests/{test_id}/review", response_model=ReviewOut, summary="Correct answers (after the test closes)")
async def review(test_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> ReviewOut:
    return ReviewOut(**await quiz_service.review(db, user_id=current.user.id, test_id=test_id))
