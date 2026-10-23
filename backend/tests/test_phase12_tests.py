"""Phase 12: knowledge tests — editor, attempts, server-side timer and grading, points, review."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, BookRead, ScoreTransaction, TestActivityLog, TestAttempt, User
from app.models.enums import AttemptStatus, ReadingStatus, ReadingVerification, ScoreCategory, TestActivityType
from app.models.test import Test as TestModel
from app.security.permissions import Perm
from app.services import quizzes as quiz_service
from tests.factories import create_book, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

TEST_PERMS = (Perm.TEST_VIEW, Perm.TEST_CREATE, Perm.TEST_EDIT, Perm.TEST_PUBLISH, Perm.TEST_DELETE)
QUESTIONS = [
    {
        "type": "SINGLE_CHOICE",
        "text": "«O'tkan kunlar» muallifi kim?",
        "points": 1,
        "explanation": "Roman 1925-yilda nashr etilgan.",
        "options": [
            {"text": "Abdulla Qodiriy", "is_correct": True},
            {"text": "Cho'lpon", "is_correct": False},
            {"text": "Oybek", "is_correct": False},
        ],
    },
    {
        "type": "MULTIPLE_CHOICE",
        "text": "Romandagi qahramonlarni belgilang",
        "points": 1,
        "options": [
            {"text": "Otabek", "is_correct": True},
            {"text": "Kumush", "is_correct": True},
            {"text": "Anvar", "is_correct": False},
        ],
    },
]


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


async def _make_test(
    client: httpx.AsyncClient,
    admin: User,
    *,
    questions: list[dict[str, Any]] | None = None,
    publish: bool = True,
    **fields: Any,
) -> dict[str, Any]:
    """Create a test through the admin API (open since a minute ago) and return its admin detail."""
    now = datetime.now(UTC)
    body = {
        "title": "O'tkan kunlar bo'yicha test",
        "starts_at": (now - timedelta(minutes=1)).isoformat(),
        "ends_at": (now + timedelta(days=1)).isoformat(),
        "duration_minutes": 10,
        **fields,
    }
    created = await client.post("/api/v1/admin/tests", json=body, headers=admin_headers(admin))
    assert created.status_code == 201, created.text
    test_id = created.json()["id"]
    saved = await client.put(
        f"/api/v1/admin/tests/{test_id}/questions",
        json={"questions": questions or QUESTIONS},
        headers=admin_headers(admin),
    )
    assert saved.status_code == 200, saved.text
    if publish:
        published = await client.post(f"/api/v1/admin/tests/{test_id}/publish", headers=admin_headers(admin))
        assert published.status_code == 200, published.text
        return published.json()
    return saved.json()


def _correct(detail: dict[str, Any]) -> dict[str, list[str]]:
    return {q["id"]: [o["id"] for o in q["options"] if o["is_correct"]] for q in detail["questions"]}


def _wrong(detail: dict[str, Any]) -> dict[str, list[str]]:
    return {q["id"]: [next(o["id"] for o in q["options"] if not o["is_correct"])] for q in detail["questions"]}


async def _start(client: httpx.AsyncClient, member: User, test_id: str) -> dict[str, Any]:
    response = await client.post(f"/api/v1/tests/{test_id}/start", headers=member_headers(member))
    assert response.status_code == 200, response.text
    return response.json()


async def _submit(
    client: httpx.AsyncClient, member: User, test_id: str, answers: dict[str, list[str]], **extra: Any
) -> httpx.Response:
    body = {"answers": [{"question_id": q, "option_ids": o} for q, o in answers.items()], **extra}
    return await client.post(f"/api/v1/tests/{test_id}/submit", json=body, headers=member_headers(member))


async def _run_out_of_time(db: AsyncSession, seconds_ago: int, attempt_id: str | None = None) -> None:
    """Test-only time travel: move an attempt (or all attempts) so its deadline passed ``seconds_ago``."""
    now = datetime.now(UTC)
    statement = update(TestAttempt).values(
        started_at=now - timedelta(minutes=30), deadline_at=now - timedelta(seconds=seconds_ago)
    )
    if attempt_id is not None:
        statement = statement.where(TestAttempt.id == uuid.UUID(attempt_id))
    await db.execute(statement)
    await db.commit()


async def _test_points(db: AsyncSession, user: User | uuid.UUID, *categories: ScoreCategory) -> int:
    categories = categories or (ScoreCategory.TEST,)
    user_id = user if isinstance(user, uuid.UUID) else user.id
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(
                ScoreTransaction.user_id == user_id, ScoreTransaction.category.in_(categories)
            )
        )
    )


# ---------------------------------------------------------------------------- admin editor


async def test_editor_validation_publish_and_audit(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    detail = await _make_test(client, admin, publish=False)
    assert detail["max_score"] == 20  # default from settings
    assert detail["status"] == "DRAFT"
    assert detail["question_count"] == 2
    test_id = detail["id"]

    two_correct = [{**QUESTIONS[0], "options": [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": True}]}]
    bad = await client.put(
        f"/api/v1/admin/tests/{test_id}/questions", json={"questions": two_correct}, headers=admin_headers(admin)
    )
    assert bad.status_code == 422
    one_option = [{**QUESTIONS[0], "options": [{"text": "A", "is_correct": True}]}]
    assert (
        await client.put(
            f"/api/v1/admin/tests/{test_id}/questions", json={"questions": one_option}, headers=admin_headers(admin)
        )
    ).status_code == 422
    passing_too_high = await client.patch(
        f"/api/v1/admin/tests/{test_id}", json={"passing_score": 50}, headers=admin_headers(admin)
    )
    assert passing_too_high.status_code == 400

    published = await client.post(f"/api/v1/admin/tests/{test_id}/publish", headers=admin_headers(admin))
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"
    assert published.json()["state"] == "OPEN"
    again = await client.post(f"/api/v1/admin/tests/{test_id}/publish", headers=admin_headers(admin))
    assert again.status_code == 409

    actions = set(await db.scalars(select(AuditLog.action).where(AuditLog.entity_id == test_id)))
    assert {"TEST_CREATE", "TEST_QUESTIONS_UPDATE", "TEST_PUBLISH"} <= actions


async def test_publish_requires_questions(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    now = datetime.now(UTC)
    created = await client.post(
        "/api/v1/admin/tests",
        json={"title": "Bo'sh test", "starts_at": now.isoformat(), "ends_at": (now + timedelta(hours=1)).isoformat()},
        headers=admin_headers(admin),
    )
    response = await client.post(f"/api/v1/admin/tests/{created.json()['id']}/publish", headers=admin_headers(admin))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TEST_HAS_NO_QUESTIONS"


async def test_test_permissions(client: httpx.AsyncClient, db: AsyncSession) -> None:
    viewer = await _admin(db, Perm.TEST_VIEW)
    member = await create_user(db)
    await db.commit()
    body = {"title": "Test", "starts_at": datetime.now(UTC).isoformat(), "ends_at": "2099-01-01T00:00:00+05:00"}
    assert (await client.post("/api/v1/admin/tests", json=body, headers=admin_headers(viewer))).status_code == 403
    assert (await client.get("/api/v1/admin/tests", headers=admin_headers(viewer))).status_code == 200
    assert (await client.get("/api/v1/admin/tests", headers=member_headers(member))).status_code == 403
    assert (await client.get("/api/v1/tests")).status_code == 401


async def test_drafts_are_hidden_from_members(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    draft = await _make_test(client, admin, publish=False)
    assert (await client.get("/api/v1/tests", headers=member_headers(member))).json() == []
    assert (await client.get(f"/api/v1/tests/{draft['id']}", headers=member_headers(member))).status_code == 404
    assert (await client.post(f"/api/v1/tests/{draft['id']}/start", headers=member_headers(member))).status_code == 404


# ---------------------------------------------------------------------------- attempts and grading


async def test_correct_answers_are_never_sent_before_close(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    attempt = await _start(client, member, detail["id"])
    listing = await client.get("/api/v1/tests", headers=member_headers(member))
    for payload in (attempt, listing.json()):
        text = json.dumps(payload)
        assert "is_correct" not in text
        assert "explanation" not in text
    assert len(attempt["questions"]) == 2
    assert all(len(q["options"]) == 3 for q in attempt["questions"])
    review = await client.get(f"/api/v1/tests/{detail['id']}/review", headers=member_headers(member))
    assert review.status_code == 403


async def test_correct_answers_earn_points_and_wrong_earn_zero(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    good, bad = await create_user(db), await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)

    await _start(client, good, detail["id"])
    result = await _submit(client, good, detail["id"], _correct(detail))
    assert result.status_code == 200, result.text
    assert result.json()["score"] == 20
    assert result.json()["correct_count"] == 2
    assert result.json()["points_awarded"] == 20
    assert await _test_points(db, good) == 20

    await _start(client, bad, detail["id"])
    result = await _submit(client, bad, detail["id"], _wrong(detail))
    assert result.json()["score"] == 0
    assert result.json()["passed"] is False
    assert await _test_points(db, bad) == 0


async def test_multiple_choice_is_all_or_nothing_and_score_is_scaled(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    answers = _correct(detail)
    multi = next(q for q in detail["questions"] if q["type"] == "MULTIPLE_CHOICE")
    answers[multi["id"]] = answers[multi["id"]][:1]  # only one of the two correct options

    await _start(client, member, detail["id"])
    result = (await _submit(client, member, detail["id"], answers)).json()
    assert result["correct_count"] == 1
    assert result["score"] == 10  # 1 of 2 question points × 20


async def test_client_supplied_score_is_ignored(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    await _start(client, member, detail["id"])
    result = await _submit(client, member, detail["id"], _wrong(detail), score=20, points_awarded=20)
    assert result.status_code == 200
    assert result.json()["score"] == 0
    assert await _test_points(db, member) == 0


async def test_answers_are_saved_one_by_one_and_validated(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    test_id = detail["id"]
    attempt = await _start(client, member, test_id)
    single = next(q for q in detail["questions"] if q["type"] == "SINGLE_CHOICE")
    multi = next(q for q in detail["questions"] if q["type"] == "MULTIPLE_CHOICE")
    headers = member_headers(member)

    two = {"question_id": single["id"], "option_ids": [o["id"] for o in single["options"][:2]]}
    assert (await client.post(f"/api/v1/tests/{test_id}/answer", json=two, headers=headers)).status_code == 400
    foreign = {"question_id": single["id"], "option_ids": [multi["options"][0]["id"]]}
    assert (await client.post(f"/api/v1/tests/{test_id}/answer", json=foreign, headers=headers)).status_code == 400

    for question_id, option_ids in _correct(detail).items():
        saved = await client.post(
            f"/api/v1/tests/{test_id}/answer",
            json={"question_id": question_id, "option_ids": option_ids},
            headers=headers,
        )
        assert saved.status_code == 200
    resumed = await client.get(f"/api/v1/tests/{test_id}/attempt", headers=headers)
    assert resumed.json()["attempt_id"] == attempt["attempt_id"]
    assert resumed.json()["answers"] == _correct(detail)
    # Submitting without a body grades the answers already saved on the server.
    result = await client.post(f"/api/v1/tests/{test_id}/submit", json={}, headers=headers)
    assert result.json()["score"] == 20


async def test_submit_is_idempotent(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    await _start(client, member, detail["id"])
    first = await _submit(client, member, detail["id"], _correct(detail))
    second = await _submit(client, member, detail["id"], _wrong(detail))
    assert second.status_code == 200
    assert second.json()["attempt_id"] == first.json()["attempt_id"]
    assert second.json()["score"] == 20
    assert await _test_points(db, member) == 20


async def test_start_resumes_and_parallel_starts_create_one_attempt(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    responses = await asyncio.gather(
        *[client.post(f"/api/v1/tests/{detail['id']}/start", headers=member_headers(member)) for _ in range(5)]
    )
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    assert len({r.json()["attempt_id"] for r in responses}) == 1
    assert await db.scalar(select(func.count()).select_from(TestAttempt)) == 1
    again = await _start(client, member, detail["id"])
    assert again["attempt_id"] == responses[0].json()["attempt_id"]
    reconnects = await db.scalar(
        select(func.count())
        .select_from(TestActivityLog)
        .where(TestActivityLog.event_type == TestActivityType.RECONNECTED)
    )
    assert reconnects >= 1


async def test_deadline_is_fixed_by_server(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    soon = datetime.now(UTC) + timedelta(minutes=3)
    detail = await _make_test(client, admin, duration_minutes=10, ends_at=soon.isoformat())
    attempt = await _start(client, member, detail["id"])
    deadline = datetime.fromisoformat(attempt["deadline_at"])
    # The test closes in 3 minutes, so the 10-minute timer is cut to the test end.
    assert abs((deadline - soon).total_seconds()) < 1


async def test_expired_attempt_rejects_answers_but_keeps_earlier_ones(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    test_id = detail["id"]
    attempt = await _start(client, member, test_id)
    single = next(q for q in detail["questions"] if q["type"] == "SINGLE_CHOICE")
    correct = _correct(detail)
    await client.post(
        f"/api/v1/tests/{test_id}/answer",
        json={"question_id": single["id"], "option_ids": correct[single["id"]]},
        headers=member_headers(member),
    )
    # The clock runs out (the client's timer may still show time left — the server wins).
    await _run_out_of_time(db, 30, attempt["attempt_id"])

    member_id = member.id
    late = await _submit(client, member, test_id, correct)
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "TEST_TIME_EXPIRED"
    db.expire_all()
    stored = await db.get(TestAttempt, uuid.UUID(attempt["attempt_id"]))
    assert stored.status == AttemptStatus.EXPIRED
    assert stored.correct_count == 1  # the answer saved in time counts
    assert stored.score == 10
    assert await _test_points(db, member_id) == 10
    timeout = await db.scalar(
        select(func.count()).select_from(TestActivityLog).where(TestActivityLog.event_type == TestActivityType.TIMEOUT)
    )
    assert timeout == 1


async def test_overdue_attempts_are_graded_when_member_returns(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    attempt = await _start(client, member, detail["id"])
    await _run_out_of_time(db, 60, attempt["attempt_id"])
    listing = (await client.get("/api/v1/tests", headers=member_headers(member))).json()
    assert listing[0]["attempts"][0]["status"] == "EXPIRED"
    assert listing[0]["in_progress"] is False
    assert listing[0]["can_start"] is False  # only one attempt allowed


async def test_closed_and_upcoming_tests_cannot_be_started(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    later = datetime.now(UTC) + timedelta(days=1)
    upcoming = await _make_test(
        client, admin, starts_at=later.isoformat(), ends_at=(later + timedelta(hours=1)).isoformat()
    )
    response = await client.post(f"/api/v1/tests/{upcoming['id']}/start", headers=member_headers(member))
    assert response.json()["error"]["code"] == "TEST_NOT_STARTED"

    closed = await _make_test(client, admin)
    await client.post(f"/api/v1/admin/tests/{closed['id']}/close", headers=admin_headers(admin))
    response = await client.post(f"/api/v1/tests/{closed['id']}/start", headers=member_headers(member))
    assert response.json()["error"]["code"] == "TEST_CLOSED"


async def test_attempt_limit(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    await _start(client, member, detail["id"])
    await _submit(client, member, detail["id"], _wrong(detail))
    response = await client.post(f"/api/v1/tests/{detail['id']}/start", headers=member_headers(member))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_ATTEMPTS_LEFT"


async def test_best_attempt_counts_once(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin, attempts_allowed=3)
    half = _correct(detail)
    multi = next(q for q in detail["questions"] if q["type"] == "MULTIPLE_CHOICE")
    half[multi["id"]] = []

    await _start(client, member, detail["id"])
    assert (await _submit(client, member, detail["id"], half)).json()["points_awarded"] == 10
    await _start(client, member, detail["id"])
    assert (await _submit(client, member, detail["id"], _correct(detail))).json()["points_awarded"] == 10
    await _start(client, member, detail["id"])
    assert (await _submit(client, member, detail["id"], _wrong(detail))).json()["points_awarded"] == 0
    assert await _test_points(db, member) == 20  # = the best attempt, never more


async def test_below_passing_score_earns_nothing(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin, passing_score=15)
    half = _correct(detail)
    multi = next(q for q in detail["questions"] if q["type"] == "MULTIPLE_CHOICE")
    half[multi["id"]] = []
    await _start(client, member, detail["id"])
    result = (await _submit(client, member, detail["id"], half)).json()
    assert result["score"] == 10
    assert result["passed"] is False
    assert result["points_awarded"] == 0
    assert await _test_points(db, member) == 0


async def test_passing_a_book_test_verifies_reading(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    book = await create_book(db)
    await db.commit()
    detail = await _make_test(client, admin, book_id=str(book.id), passing_score=10)
    await _start(client, member, detail["id"])
    await _submit(client, member, detail["id"], _correct(detail))
    read = await db.scalar(select(BookRead).where(BookRead.user_id == member.id, BookRead.book_id == book.id))
    assert read.status == ReadingStatus.COMPLETED
    assert read.verification_source == ReadingVerification.TEST
    assert await _test_points(db, member, ScoreCategory.BOOK_COMPLETION) == 10


# ---------------------------------------------------------------------------- closing, bonuses and review


async def test_close_awards_place_bonuses_once_and_opens_review(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    first, second, third, fourth = [await create_user(db) for _ in range(4)]
    await db.commit()
    detail = await _make_test(client, admin)
    test_id = detail["id"]
    half = _correct(detail)
    multi = next(q for q in detail["questions"] if q["type"] == "MULTIPLE_CHOICE")
    half[multi["id"]] = []
    for member, answers in ((first, _correct(detail)), (second, half), (third, half), (fourth, _wrong(detail))):
        await _start(client, member, test_id)
        await _submit(client, member, test_id, answers)
    # second and third have equal scores: the faster one ranks higher.
    for member, seconds in ((second, 100), (third, 50)):
        await db.execute(
            update(TestAttempt)
            .where(TestAttempt.user_id == member.id)
            .values(started_at=TestAttempt.submitted_at - timedelta(seconds=seconds))
        )
    await db.commit()

    closed = await client.post(f"/api/v1/admin/tests/{test_id}/close", headers=admin_headers(admin))
    assert closed.status_code == 200
    assert closed.json()["state"] == "CLOSED"
    assert closed.json()["rank_bonus_awarded"] is True
    await client.post(f"/api/v1/admin/tests/{test_id}/close", headers=admin_headers(admin))  # repeated: no-op

    bonus = ScoreCategory.TEST_RANK_BONUS
    assert [await _test_points(db, m, bonus) for m in (first, third, second, fourth)] == [10, 5, 3, 0]

    review = await client.get(f"/api/v1/tests/{test_id}/review", headers=member_headers(third))
    assert review.status_code == 200
    body = review.json()
    assert body["place"] == 2
    assert body["participants"] == 3  # the member without points is not ranked
    single = next(q for q in body["questions"] if q["type"] == "SINGLE_CHOICE")
    assert single["is_correct"] is True
    assert single["explanation"] == "Roman 1925-yilda nashr etilgan."
    assert any(o["is_correct"] and o["selected"] for o in single["options"])


async def test_scheduler_closes_ended_tests(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    await _start(client, member, detail["id"])
    await client.post(
        f"/api/v1/tests/{detail['id']}/answer",
        json={
            "question_id": detail["questions"][0]["id"],
            "option_ids": _correct(detail)[detail["questions"][0]["id"]],
        },
        headers=member_headers(member),
    )
    past = datetime.now(UTC) - timedelta(minutes=1)
    await db.execute(
        update(TestModel)
        .where(TestModel.id == uuid.UUID(detail["id"]))
        .values(starts_at=past - timedelta(hours=1), ends_at=past)
    )
    await db.commit()
    await _run_out_of_time(db, 60)

    member_id = member.id
    assert await quiz_service.close_ended_tests(db) == 1
    db.expire_all()
    attempt = await db.scalar(select(TestAttempt))
    assert attempt.status == AttemptStatus.EXPIRED
    assert attempt.score == 10
    assert await _test_points(db, member_id, ScoreCategory.TEST_RANK_BONUS) == 10
    assert await quiz_service.close_ended_tests(db) == 0


async def test_results_are_locked_after_attempts(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    test_id = detail["id"]
    await _start(client, member, test_id)
    headers = admin_headers(admin)
    questions = await client.put(
        f"/api/v1/admin/tests/{test_id}/questions", json={"questions": QUESTIONS}, headers=headers
    )
    assert questions.status_code == 409
    assert (
        await client.patch(f"/api/v1/admin/tests/{test_id}", json={"max_score": 50}, headers=headers)
    ).status_code == 409
    extended = await client.patch(
        f"/api/v1/admin/tests/{test_id}", json={"title": "Yangi nom", "max_score": 20}, headers=headers
    )
    assert extended.status_code == 200
    assert (await client.delete(f"/api/v1/admin/tests/{test_id}", headers=headers)).status_code == 409
    assert (await client.post(f"/api/v1/admin/tests/{test_id}/unpublish", headers=headers)).status_code == 409


async def test_activity_signals_and_admin_results(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db, first_name="Dilnoza", last_name="Karimova")
    await db.commit()
    detail = await _make_test(client, admin)
    test_id = detail["id"]
    await _start(client, member, test_id)
    signals = await client.post(
        f"/api/v1/tests/{test_id}/activity",
        json={
            "events": [
                {"type": "VISIBILITY_HIDDEN", "client_time": datetime.now(UTC).isoformat()},
                {"type": "VISIBILITY_VISIBLE"},
                {"type": "FOCUS_LOST", "details": {"seconds": 12}},
            ]
        },
        headers=member_headers(member),
    )
    assert signals.status_code == 204
    await _submit(client, member, test_id, _correct(detail))

    results = await client.get(f"/api/v1/admin/tests/{test_id}/results", headers=admin_headers(admin))
    assert results.status_code == 200
    body = results.json()
    assert body["participants"] == 1
    assert body["passed"] == 1
    row = body["items"][0]
    assert row["last_name"] == "Karimova"
    assert row["score"] == 20
    # VISIBILITY_HIDDEN + FOCUS_LOST; "visible again" is neutral, and 2 answers are too few for FAST_ANSWER
    assert row["signals"] == 2

    attempt = await client.get(f"/api/v1/admin/test-attempts/{row['attempt_id']}", headers=admin_headers(admin))
    assert attempt.status_code == 200
    assert {item["type"] for item in attempt.json()["activity"]} >= {"VISIBILITY_HIDDEN", "FOCUS_LOST"}
    assert all(answer["is_correct"] for answer in attempt.json()["answers"])

    csv_response = await client.get(f"/api/v1/admin/tests/{test_id}/results.csv", headers=admin_headers(admin))
    assert csv_response.status_code == 200
    assert "Karimova" in csv_response.text
    assert csv_response.text.startswith("﻿")


async def test_fast_answers_are_flagged_as_a_signal(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    questions = [
        {"text": f"Savol {i}", "options": [{"text": "Ha", "is_correct": True}, {"text": "Yo'q"}]} for i in range(4)
    ]
    detail = await _make_test(client, admin, questions=questions)
    await _start(client, member, detail["id"])
    await _submit(client, member, detail["id"], _correct(detail))
    fast = await db.scalar(select(TestActivityLog).where(TestActivityLog.event_type == TestActivityType.FAST_ANSWER))
    assert fast is not None
    assert fast.details["answered"] == 4


def test_scale_rounds_half_up() -> None:
    assert quiz_service.scale(1, 2, 20) == 10
    assert quiz_service.scale(1, 3, 20) == 7  # 6.67
    assert quiz_service.scale(1, 8, 20) == 3  # 2.5 → 3
    assert quiz_service.scale(0, 5, 20) == 0
    assert quiz_service.scale(5, 5, 20) == 20


async def test_permanent_test_is_unlimited_and_pays_only_the_first_perfect(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """Q13 «Doimiy test»: attempts are unlimited (attempts_allowed is ignored) and the only points are
    a one-time bonus for the first perfect result — nothing for a non-perfect attempt, nothing again."""
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin, kind="PERMANENT")  # attempts_allowed defaults to 1
    test_id = detail["id"]
    assert detail["kind"] == "PERMANENT"
    assert detail["max_score"] == 3  # tests.permanent_perfect_points
    correct, wrong = _correct(detail), _wrong(detail)

    # Attempt 1 — not perfect → no points, but the attempt is allowed.
    await _start(client, member, test_id)
    r1 = await _submit(client, member, test_id, wrong)
    assert r1.status_code == 200, r1.text
    assert r1.json()["points_awarded"] == 0

    # Attempt 2 — a permanent test ignores the 1-attempt limit, so this starts and grades fine.
    await _start(client, member, test_id)
    r2 = await _submit(client, member, test_id, correct)
    assert r2.status_code == 200, r2.text
    assert r2.json()["points_awarded"] == 3  # first perfect → flat bonus
    assert await _test_points(db, member) == 3

    # Attempt 3 — perfect again → the bonus is not paid twice.
    await _start(client, member, test_id)
    r3 = await _submit(client, member, test_id, correct)
    assert r3.status_code == 200, r3.text
    assert r3.json()["points_awarded"] == 0
    assert await _test_points(db, member) == 3
