"""Phase 2: schema, migrations, reference data and database-level integrity rules."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.models import (
    AttendanceRecord,
    AttendanceSession,
    AuditLog,
    Base,
    NotificationTemplate,
    Permission,
    Role,
    ScoreTransaction,
    Season,
    SystemSetting,
    TestAttempt,
)
from app.models.enums import AttemptStatus, AttendanceMethod, NotificationType, ScoreCategory
from app.security.permissions import Perm
from app.services.bootstrap import sync_reference_data
from app.services.settings import SETTING_DEFINITIONS, get_all_settings, get_setting
from tests.conftest import alembic_config
from tests.factories import create_event, create_test, create_user, now

# ---------------------------------------------------------------------------- schema


async def test_migrations_match_models(db: AsyncSession) -> None:
    """`alembic check` fails if the models and the migration history have drifted apart."""
    await asyncio.to_thread(command.check, alembic_config())


async def test_all_tables_created(db: AsyncSession) -> None:
    rows = await db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    existing = {row[0] for row in rows}
    assert set(Base.metadata.tables) <= existing
    assert len(Base.metadata.tables) >= 38


# ---------------------------------------------------------------------------- reference data


async def test_reference_data_seeded(db: AsyncSession) -> None:
    assert await db.scalar(select(func.count()).select_from(Permission)) == len(Perm)
    roles = set(await db.scalars(select(Role.code)))
    assert roles == {"SUPER_ADMIN", "ADMIN", "USER"}
    assert await db.scalar(select(func.count()).select_from(SystemSetting)) == len(SETTING_DEFINITIONS)
    template_types = set(await db.scalars(select(NotificationTemplate.type)))
    assert template_types == set(NotificationType)


async def test_default_score_rules(db: AsyncSession) -> None:
    settings = await get_all_settings(db)
    assert settings["score.attendance_points"] == 30
    assert settings["score.test_max_points"] == 20
    assert settings["score.test_rank_bonus"] == [10, 5, 3]
    assert settings["score.book_completion_points"] == 10


async def test_bootstrap_is_idempotent_and_keeps_admin_changes(db: AsyncSession) -> None:
    setting = await db.get(SystemSetting, "score.attendance_points")
    assert setting is not None
    setting.value = 25
    await db.commit()

    await sync_reference_data(db)
    await sync_reference_data(db)

    assert await get_setting(db, "score.attendance_points") == 25
    assert await db.scalar(select(func.count()).select_from(Permission)) == len(Perm)


async def test_invalid_stored_setting_falls_back_to_default(db: AsyncSession) -> None:
    setting = await db.get(SystemSetting, "score.attendance_points")
    assert setting is not None
    setting.value = "not a number"
    await db.commit()
    assert await get_setting(db, "score.attendance_points") == 30


# ---------------------------------------------------------------------------- uniqueness


async def test_telegram_id_is_unique(db: AsyncSession) -> None:
    await create_user(db, telegram_id=555)
    with pytest.raises(IntegrityError):
        await create_user(db, telegram_id=555)


async def test_phone_is_unique(db: AsyncSession) -> None:
    await create_user(db, phone="+998901112233")
    with pytest.raises(IntegrityError):
        await create_user(db, phone="+998901112233")


async def test_users_without_phone_allowed(db: AsyncSession) -> None:
    await create_user(db, phone=None)
    await create_user(db, phone=None)
    await db.commit()


async def test_course_range_enforced(db: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await create_user(db, course=12)


async def test_duplicate_attendance_rejected_by_database(db: AsyncSession) -> None:
    user = await create_user(db)
    event = await create_event(db)
    db.add(AttendanceRecord(event_id=event.id, user_id=user.id, method=AttendanceMethod.QR))
    await db.flush()
    db.add(AttendanceRecord(event_id=event.id, user_id=user.id, method=AttendanceMethod.CODE))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_concurrent_attendance_creates_single_record(db: AsyncSession) -> None:
    """Two simultaneous check-ins for the same member and event: exactly one succeeds."""
    user = await create_user(db)
    event = await create_event(db)
    await db.commit()

    async def check_in() -> bool:
        async with get_session_factory()() as session:
            session.add(AttendanceRecord(event_id=event.id, user_id=user.id, method=AttendanceMethod.QR))
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    results = await asyncio.gather(*(check_in() for _ in range(5)))
    assert results.count(True) == 1
    count = await db.scalar(
        select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.event_id == event.id)
    )
    assert count == 1


async def test_only_one_open_attendance_session_per_event(db: AsyncSession) -> None:
    event = await create_event(db)
    db.add(AttendanceSession(event_id=event.id, closes_at=now() + timedelta(minutes=10)))
    await db.flush()
    db.add(AttendanceSession(event_id=event.id, closes_at=now() + timedelta(minutes=10)))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_only_one_in_progress_attempt(db: AsyncSession) -> None:
    user = await create_user(db)
    test = await create_test(db)

    def attempt(number: int) -> TestAttempt:
        return TestAttempt(
            test_id=test.id,
            user_id=user.id,
            attempt_number=number,
            status=AttemptStatus.IN_PROGRESS,
            deadline_at=now() + timedelta(minutes=15),
            question_order=[],
            option_order={},
        )

    db.add(attempt(1))
    await db.flush()
    db.add(attempt(2))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_only_one_current_season(db: AsyncSession) -> None:
    db.add(Season(name="2026 Kuz", starts_on=date(2026, 9, 1), ends_on=date(2026, 12, 31), is_current=True))
    await db.flush()
    db.add(Season(name="2027 Bahor", starts_on=date(2027, 2, 1), ends_on=date(2027, 6, 30), is_current=True))
    with pytest.raises(IntegrityError):
        await db.flush()


# ---------------------------------------------------------------------------- score ledger


async def _transaction(db: AsyncSession, **overrides) -> ScoreTransaction:
    user = overrides.pop("user", None) or await create_user(db)
    values = {
        "user_id": user.id,
        "amount": 30,
        "category": ScoreCategory.ATTENDANCE,
        "idempotency_key": f"attendance:{uuid.uuid4()}",
    }
    values.update(overrides)
    transaction = ScoreTransaction(**values)
    db.add(transaction)
    await db.flush()
    return transaction


async def test_score_idempotency_key_prevents_double_award(db: AsyncSession) -> None:
    user = await create_user(db)
    await _transaction(db, user=user, idempotency_key="attendance:same")
    with pytest.raises(IntegrityError):
        await _transaction(db, user=user, idempotency_key="attendance:same")


async def test_zero_amount_rejected(db: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await _transaction(db, amount=0)


async def test_manual_score_requires_reason(db: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await _transaction(db, category=ScoreCategory.MANUAL, amount=5, reason=None)


async def test_manual_score_with_reason_accepted(db: AsyncSession) -> None:
    transaction = await _transaction(
        db, category=ScoreCategory.MANUAL, amount=5, reason="Texnik nosozlik tasdiqlangani sababli tuzatildi"
    )
    assert transaction.id is not None


@pytest.mark.parametrize("statement", ["UPDATE score_transactions SET amount = 999", "DELETE FROM score_transactions"])
async def test_score_ledger_is_append_only(db: AsyncSession, statement: str) -> None:
    await _transaction(db)
    await db.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(text(statement))
    await db.rollback()


# ---------------------------------------------------------------------------- audit log


@pytest.mark.parametrize("statement", ["UPDATE audit_logs SET reason = 'x'", "DELETE FROM audit_logs"])
async def test_audit_log_is_append_only(db: AsyncSession, statement: str) -> None:
    db.add(AuditLog(action="USER_BLOCK", entity_type="user", entity_id=str(uuid.uuid4()), reason="test"))
    await db.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(text(statement))
    await db.rollback()
    assert await db.scalar(select(func.count()).select_from(AuditLog)) == 1


async def test_institute_faculties_seeded_by_migration(db: AsyncSession) -> None:
    from app.models import Faculty

    config = alembic_config()
    await asyncio.to_thread(command.downgrade, config, "0002")
    await asyncio.to_thread(command.upgrade, config, "head")
    names = list(await db.scalars(select(Faculty.name).order_by(Faculty.sort_order)))
    # Owner's corrected order (migration 0027): preventive medicine first, then the rest.
    assert names == ["Tibbiy profilaktika va jamoat salomatligi", "Davolash ishi", "Pediatriya", "Xalqaro fakultet"]
    await db.commit()  # end the read before the schema changes again (dropping tables waits for open reads)
    # Re-running is harmless (no duplicates).
    await asyncio.to_thread(command.downgrade, config, "0002")
    await asyncio.to_thread(command.upgrade, config, "head")
    assert await db.scalar(select(func.count()).select_from(Faculty)) == 4


async def test_organization_name_default(db: AsyncSession) -> None:
    assert await get_setting(db, "org.organization_name") == "Farg'ona jamoat salomatligi tibbiyot instituti"
