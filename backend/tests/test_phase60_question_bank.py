"""Round L1: a test's questions as a bank — every member gets the chosen number of them at random,
another attempt brings questions not seen yet, and the score is the share of correct answers."""

from __future__ import annotations

import itertools
import uuid
from typing import Any

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TestQuestion
from tests.factories import create_user
from tests.helpers import admin_headers, member_headers
from tests.test_phase12_tests import TEST_PERMS, _admin, _make_test, _start, _submit

_ids = itertools.count(3_400_000)


def _bank(size: int) -> list[dict[str, Any]]:
    return [
        {
            "type": "SINGLE_CHOICE",
            "text": f"{number}-savol: kitobning {number}-bobida nima bo'ldi?",
            "points": 1,
            "options": [{"text": "To'g'ri javob", "is_correct": True}, {"text": "Noto'g'ri", "is_correct": False}],
        }
        for number in range(1, size + 1)
    ]


async def test_every_member_gets_a_random_part_of_the_bank(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    test = await _make_test(client, admin, questions=_bank(12), publish=False, questions_per_attempt=5)
    assert test["question_count"] == 12 and test["questions_per_attempt"] == 5

    # more than the bank holds cannot be published
    too_many = await client.patch(
        f"/api/v1/admin/tests/{test['id']}", json={"questions_per_attempt": 20}, headers=admin_headers(admin)
    )
    assert too_many.status_code == 200  # a draft may still get more questions
    refused = await client.post(f"/api/v1/admin/tests/{test['id']}/publish", headers=admin_headers(admin))
    assert refused.status_code == 400 and "12 ta savol" in refused.json()["error"]["message"]
    url = f"/api/v1/admin/tests/{test['id']}"
    await client.patch(url, json={"questions_per_attempt": 5}, headers=admin_headers(admin))
    published = await client.post(f"/api/v1/admin/tests/{test['id']}/publish", headers=admin_headers(admin))
    assert published.status_code == 200
    # once published the number cannot exceed the bank either
    over = await client.patch(
        f"/api/v1/admin/tests/{test['id']}", json={"questions_per_attempt": 13}, headers=admin_headers(admin)
    )
    assert over.status_code == 400

    members = [await create_user(db, telegram_id=next(_ids)) for _ in range(6)]
    await db.commit()
    listed = await client.get("/api/v1/tests", headers=member_headers(members[0]))
    assert next(t for t in listed.json() if t["id"] == test["id"])["question_count"] == 5

    sets = []
    for member in members:
        attempt = await _start(client, member, test["id"])
        ids = [question["id"] for question in attempt["questions"]]
        assert len(ids) == 5 and len(set(ids)) == 5
        sets.append(frozenset(ids))
    assert len(set(sets)) > 1  # not everybody got the same five

    # all five right is the full score, though the bank has twelve
    first = await _start(client, members[0], test["id"])
    answers = {q["id"]: [q["options"][0]["id"]] for q in first["questions"]}
    detail = (await client.get(f"/api/v1/admin/tests/{test['id']}", headers=admin_headers(admin))).json()
    correct = {q["id"]: [o["id"] for o in q["options"] if o["is_correct"]] for q in detail["questions"]}
    answers = {question: correct[question] for question in answers}
    result = await _submit(client, members[0], test["id"], answers)
    assert result.status_code == 200, result.text
    assert result.json()["score"] == test["max_score"] and result.json()["correct_count"] == 5

    # the number is locked once members have started
    locked = await client.patch(
        f"/api/v1/admin/tests/{test['id']}", json={"questions_per_attempt": 6}, headers=admin_headers(admin)
    )
    assert locked.status_code == 409


async def test_another_attempt_brings_new_questions(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    test = await _make_test(client, admin, questions=_bank(10), questions_per_attempt=4, attempts_allowed=2)
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    first = await _start(client, member, test["id"])
    seen = {question["id"] for question in first["questions"]}
    await _submit(client, member, test["id"], {})
    second = await _start(client, member, test["id"])
    again = {question["id"] for question in second["questions"]}
    assert len(again) == 4 and not seen & again  # the four not seen yet

    # a picture of a question outside the member's own set stays hidden until the close
    detail = (await client.get(f"/api/v1/admin/tests/{test['id']}", headers=admin_headers(admin))).json()
    other = next(q["id"] for q in detail["questions"] if q["id"] not in seen | again)
    await db.execute(
        update(TestQuestion).where(TestQuestion.id == uuid.UUID(other)).values(image_key=f"tests/{test['id']}/x.jpg")
    )
    await db.commit()
    hidden = await client.get(f"/api/v1/tests/{test['id']}/questions/{other}/image", headers=member_headers(member))
    assert hidden.status_code == 403


async def test_without_a_number_everybody_answers_everything(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *TEST_PERMS)
    test = await _make_test(client, admin, questions=_bank(3))
    assert test["questions_per_attempt"] is None
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    attempt = await _start(client, member, test["id"])
    assert len(attempt["questions"]) == 3
