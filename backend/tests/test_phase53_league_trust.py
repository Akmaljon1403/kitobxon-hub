"""Round J4: «🏛 Fakultetlar ligasi», «Faollik va qaytish» analytics and «🛡 Ishonch markazi»."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardPayment, Faculty, ReadingLog, ScoreTransaction, ShelfItem, TestAttempt
from app.models.enums import AttemptStatus, CardPaymentStatus, PaymentKind, ScoreCategory, ShelfStatus
from app.services import reading_journal
from app.services.scoring import award_points
from tests.factories import create_test, create_user
from tests.helpers import admin_headers, grant_role, member_headers

_ids = itertools.count(2_700_000)


async def test_the_faculty_league(client: httpx.AsyncClient, db: AsyncSession) -> None:
    small = Faculty(name="Pediatriya", short_name="PED")
    big = Faculty(name="Davolash ishi", short_name="DI")
    db.add_all([small, big])
    await db.flush()
    reader = await create_user(db, telegram_id=next(_ids), faculty_id=small.id)
    others = [await create_user(db, telegram_id=next(_ids), faculty_id=big.id) for _ in range(3)]
    await award_points(db, user_id=reader.id, amount=30, category=ScoreCategory.CAMPAIGN, idempotency_key="l:1")
    await award_points(db, user_id=others[0].id, amount=45, category=ScoreCategory.CAMPAIGN, idempotency_key="l:2")
    item = ShelfItem(user_id=reader.id, title="Ufq", status=ShelfStatus.FINISHED, finished_at=datetime.now(UTC))
    db.add(item)
    await db.flush()
    db.add(ReadingLog(user_id=reader.id, shelf_item_id=item.id, log_date=reading_journal.today(), pages=42))
    await db.commit()

    league = (await client.get("/api/v1/league?period=month", headers=member_headers(reader))).json()
    rows = {row["faculty"]: row for row in league["items"]}
    pediatrics, medicine = rows["Pediatriya"], rows["Davolash ishi"]
    assert pediatrics["rank"] == 1 and pediatrics["average"] == 30.0  # one member with 30 beats 45 over three
    assert (pediatrics["pages"], pediatrics["books"], pediatrics["participation"], pediatrics["mine"]) == (
        42,
        1,
        100,
        True,
    )
    assert (medicine["members"], medicine["active"], medicine["participation"], medicine["mine"]) == (3, 1, 33, False)
    bad = await client.get("/api/v1/league?period=season", headers=member_headers(reader))
    assert bad.status_code == 422


async def test_engagement_by_month(client: httpx.AsyncClient, db: AsyncSession) -> None:
    analyst = await create_user(db, telegram_id=next(_ids))
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, analyst, "ADMIN")
    forbidden = await client.get("/api/v1/admin/analytics/engagement", headers=admin_headers(analyst))
    assert forbidden.status_code == 403
    boss = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    last_month = datetime.now(UTC).replace(day=1) - timedelta(days=3)
    db.add(
        ScoreTransaction(
            user_id=member.id,
            amount=5,
            category=ScoreCategory.CAMPAIGN,
            idempotency_key="e:1",
            created_at=last_month,
        )
    )
    await award_points(db, user_id=member.id, amount=5, category=ScoreCategory.CAMPAIGN, idempotency_key="e:2")
    await db.commit()
    data = (await client.get("/api/v1/admin/analytics/engagement?months=3", headers=admin_headers(boss))).json()
    assert len(data["months"]) == 3
    this_month = data["months"][-1]
    assert this_month["active"] >= 1 and this_month["returning"] == 1 and this_month["retention"] == 100
    assert data["last_30_days"]["missions_rate"] is None and data["last_30_days"]["members"] >= 3


async def test_the_trust_centre(client: httpx.AsyncClient, db: AsyncSession) -> None:
    auditor = await create_user(db, telegram_id=next(_ids))
    plain = await create_user(db, telegram_id=next(_ids))
    member = await create_user(db, telegram_id=next(_ids), first_name="Tezkor", last_name="Talaba")
    await db.commit()
    await grant_role(db, auditor, "SUPER_ADMIN")
    await grant_role(db, plain, "ADMIN")
    assert (await client.get("/api/v1/admin/trust", headers=admin_headers(plain))).status_code == 403

    test = await create_test(db, title="Alkimyogar testi", duration_minutes=20, max_score=20)
    started = datetime.now(UTC) - timedelta(minutes=10)
    db.add(
        TestAttempt(
            test_id=test.id,
            user_id=member.id,
            status=AttemptStatus.SUBMITTED,
            started_at=started,
            deadline_at=started + timedelta(minutes=20),
            submitted_at=started + timedelta(seconds=150),
            question_order=[],
            option_order={},
            score=20,
        )
    )
    for index in range(3):
        db.add(
            ScoreTransaction(
                user_id=member.id,
                amount=10,
                category=ScoreCategory.MANUAL,
                idempotency_key=f"t:{index}",
                reason="Qo'lda",
                created_by=auditor.id,
            )
        )
    item = ShelfItem(user_id=member.id, title="Qalin kitob")
    db.add(item)
    await db.flush()
    db.add(ReadingLog(user_id=member.id, shelf_item_id=item.id, log_date=reading_journal.today(), pages=450))
    for _ in range(2):
        db.add(
            CardPayment(
                user_id=member.id,
                kind=PaymentKind.DONATION,
                amount_uzs=5000,
                receipt_key="x.jpg",
                receipt_sha256="ab" * 32,
                status=CardPaymentStatus.PENDING,
            )
        )
    await db.commit()

    data = (await client.get("/api/v1/admin/trust?days=30", headers=admin_headers(auditor))).json()
    (fast,) = data["fast_tests"]
    assert (fast["member"], fast["test"], fast["seconds"]) == ("Talaba Tezkor", "Alkimyogar testi", 150)
    assert data["manual_members"] == [{"member": "Talaba Tezkor", "changes": 3, "points": 30}]
    assert data["big_reading_days"][0]["pages"] == 450
    assert len(data["repeated_receipts"]) == 2 and data["repeated_receipts"][0]["group"] == "abababab"

    missing = await client.get("/api/v1/admin/trust/certificate?code=XXXXX-YYYYY", headers=admin_headers(auditor))
    assert missing.status_code == 404
    created = await client.post(
        "/api/v1/admin/certificates",
        json={"user_id": str(member.id), "title": "Faol kitobxon", "description": "Faol ishtiroki uchun."},
        headers=admin_headers(auditor),
    )
    code = created.json()["code"]
    found = (await client.get(f"/api/v1/admin/trust/certificate?code={code}", headers=admin_headers(auditor))).json()
    assert found["valid"] is True and found["member"] == "Talaba Tezkor" and found["title"] == "Faol kitobxon"


async def test_the_yearly_summary_carries_the_reading_trace(db: AsyncSession) -> None:
    from sqlalchemy import select

    from app.models import Notification, SavedQuote
    from app.services import lifecycle
    from app.services.settings import update_setting
    from app.utils.timezone import local_tz

    reader = await create_user(db, telegram_id=next(_ids))
    item = ShelfItem(user_id=reader.id, title="Kecha va kunduz")
    db.add(item)
    await db.flush()
    today = reading_journal.today()
    for back, pages in ((0, 20), (1, 15), (2, 10)):
        db.add(ReadingLog(user_id=reader.id, shelf_item_id=item.id, log_date=today - timedelta(days=back), pages=pages))
    db.add(SavedQuote(user_id=reader.id, text="Ilm — nur."))
    await db.commit()
    now = datetime.now(UTC)
    await update_setting(
        db, key="academic.summary_day", value=now.astimezone(local_tz()).strftime("%m-%d"), actor_id=None
    )
    assert await lifecycle.year_summaries(db, now) >= 1
    summary = await db.scalar(select(Notification).where(Notification.dedup_key.like(f"year-summary:%:{reader.id}")))
    assert "Mutolaa kundaligidagi betlar: <b>45</b>" in summary.text
    assert "Eng uzun o'qish seriyasi: <b>3 kun</b>" in summary.text
    assert "Saqlangan iqtiboslar: <b>1</b>" in summary.text and "/kartam" in summary.text
