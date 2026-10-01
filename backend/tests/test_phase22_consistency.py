"""Phase 22: all-or-nothing writes. If awarding points fails, the fact that would have earned
them (attendance, a graded test) must not be saved either — and the member can simply retry."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttendanceRecord, ScoreTransaction, TestAttempt
from app.models.enums import AttemptStatus
from tests.factories import create_user
from tests.helpers import member_headers
from tests.test_phase10_11_events_attendance import _open_event
from tests.test_phase12_tests import TEST_PERMS, _admin, _correct, _make_test, _start, _submit


async def _broken_ledger(*_: Any, **__: Any) -> None:
    raise RuntimeError("ledger unavailable")


async def _count(db: AsyncSession, model: Any) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


async def test_attendance_is_not_saved_when_points_fail(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, token = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()

    monkeypatch.setattr("app.services.attendance.award_points", _broken_ledger)
    failed = await client.post(
        "/api/v1/attendance/verify", json={"code": token["code"]}, headers=member_headers(member)
    )
    assert failed.status_code == 500
    assert "ledger" not in failed.text  # internals never reach the client
    assert await _count(db, AttendanceRecord) == 0
    assert await _count(db, ScoreTransaction) == 0

    monkeypatch.undo()
    retried = await client.post(
        "/api/v1/attendance/verify", json={"code": token["code"]}, headers=member_headers(member)
    )
    assert retried.status_code == 200, retried.text
    assert await _count(db, AttendanceRecord) == 1
    assert await _count(db, ScoreTransaction) == 1


async def test_test_result_is_not_saved_when_points_fail(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await _admin(db, *TEST_PERMS)
    member = await create_user(db)
    await db.commit()
    detail = await _make_test(client, admin)
    await _start(client, member, detail["id"])

    monkeypatch.setattr("app.services.quizzes.award_points", _broken_ledger)
    failed = await _submit(client, member, detail["id"], _correct(detail))
    assert failed.status_code == 500
    statuses = list(await db.scalars(select(TestAttempt.status)))
    assert statuses == [AttemptStatus.IN_PROGRESS]  # grading rolled back with the points
    assert await _count(db, ScoreTransaction) == 0

    monkeypatch.undo()
    retried = await _submit(client, member, detail["id"], _correct(detail))
    assert retried.status_code == 200, retried.text
    assert retried.json()["points_awarded"] == 20
    assert await _count(db, ScoreTransaction) == 1
