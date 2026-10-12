"""Round K3: Premium as a gift to many at once — everybody, a faculty, a course or a group."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Faculty, Notification, PremiumSubscription
from app.models.enums import PremiumSource, UserStatus
from app.services import premium
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role

_ids = itertools.count(3_000_000)


async def test_premium_for_a_faculty_course_or_everybody(client: httpx.AsyncClient, db: AsyncSession) -> None:
    faculty = Faculty(name="Pediatriya", short_name="PED")
    db.add(faculty)
    await db.flush()
    boss = await create_user(db, telegram_id=next(_ids))
    second_year = [await create_user(db, telegram_id=next(_ids), faculty_id=faculty.id, course=2) for _ in range(3)]
    other_course = await create_user(db, telegram_id=next(_ids), faculty_id=faculty.id, course=3, group_name="301")
    elsewhere = await create_user(db, telegram_id=next(_ids), course=2)
    gone = await create_user(db, telegram_id=next(_ids), faculty_id=faculty.id, course=2, status=UserStatus.LEFT)
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    paying = second_year[0]
    already_until = datetime.now(UTC) + timedelta(days=10)
    db.add(
        PremiumSubscription(
            user_id=paying.id, source=PremiumSource.STARS, starts_at=datetime.now(UTC), ends_at=already_until
        )
    )
    await db.commit()

    url = "/api/v1/admin/premium/grant-bulk"
    plain = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, plain, "ADMIN")
    assert (await client.post(url, json={"days": 7, "dry_run": True}, headers=admin_headers(plain))).status_code == 403

    count = await client.post(
        url, json={"days": 7, "faculty_id": str(faculty.id), "course": 2, "dry_run": True}, headers=admin_headers(boss)
    )
    assert count.json() == {"recipients": 3}  # not the left member, not another course or faculty
    fresh_only = await client.post(
        url,
        json={"days": 7, "faculty_id": str(faculty.id), "course": 2, "only_without_premium": True, "dry_run": True},
        headers=admin_headers(boss),
    )
    assert fresh_only.json() == {"recipients": 2}

    given = await client.post(
        url,
        json={"days": 7, "faculty_id": str(faculty.id), "course": 2, "note": "Bilimlar kuni munosabati bilan"},
        headers=admin_headers(boss),
    )
    assert given.status_code == 200 and given.json()["recipients"] == 3
    # the paying member gets the days after their own period
    until = await premium.premium_until(db, paying.id)
    assert until is not None and until > already_until + timedelta(days=6)
    for member in (other_course, elsewhere, gone):
        assert not await premium.is_premium(db, member.id)
    told = list(await db.scalars(select(Notification).where(Notification.dedup_key.like("premium:gift:%"))))
    assert len(told) == 3 and "Bilimlar kuni munosabati bilan" in told[0].text
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "PREMIUM_GRANT_BULK"))
    assert audit.after["recipients"] == 3 and audit.after["target"] == "Pediatriya, 2-kurs"

    group = await client.post(url, json={"days": 3, "group_name": "301"}, headers=admin_headers(boss))
    assert group.json()["recipients"] == 1 and await premium.is_premium(db, other_course.id)

    everybody = await client.post(url, json={"days": 1, "dry_run": True}, headers=admin_headers(boss))
    # all active registered members except the super admin (for life already)
    active = await db.scalar(select(func.count()).select_from(premium.gift_audience().subquery()))
    assert everybody.json()["recipients"] == active and boss.id not in set(await db.scalars(premium.gift_audience()))

    nobody = await client.post(url, json={"days": 5, "group_name": "999"}, headers=admin_headers(boss))
    assert nobody.status_code == 409
    too_long = await client.post(url, json={"days": 400}, headers=admin_headers(boss))
    assert too_long.status_code == 422
