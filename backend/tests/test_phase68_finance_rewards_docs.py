"""Round M8: «Hujjatlar» gains money and rewards reports — confirmed card/Stars income and the
rewards given in a period, in Excel/Word/PDF like the other documents."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardPayment, Payment, Reward, User, UserReward
from app.models.enums import (
    CardPaymentStatus,
    PaymentKind,
    PaymentStatus,
    RewardType,
    UserRewardStatus,
)
from app.services import documents
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role

_ids = itertools.count(4_300_000)


async def _data(db: AsyncSession) -> dict[str, User]:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmal", last_name="Bosh")
    member = await create_user(db, telegram_id=next(_ids), first_name="Nodir", last_name="Qodirov")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    now = datetime.now(UTC)
    db.add(
        CardPayment(
            user_id=member.id,
            kind=PaymentKind.PREMIUM,
            amount_uzs=50000,
            receipt_key="receipts/x.jpg",
            status=CardPaymentStatus.APPROVED,
            decided_at=now,
            decided_by=boss.id,
        )
    )
    # a pending card payment must NOT be counted (not real income yet)
    db.add(
        CardPayment(
            user_id=member.id,
            kind=PaymentKind.PREMIUM,
            amount_uzs=999000,
            receipt_key="receipts/y.jpg",
            status=CardPaymentStatus.PENDING,
        )
    )
    db.add(
        Payment(
            user_id=member.id,
            kind=PaymentKind.DONATION,
            amount=100,
            invoice_payload="donate",
            telegram_charge_id=f"charge-{next(_ids)}",
            status=PaymentStatus.PAID,
        )
    )
    reward = Reward(title="Bepul Premium 30 kun", type=RewardType.SUBSCRIPTION_CODE)
    db.add(reward)
    await db.flush()
    db.add(
        UserReward(
            user_id=member.id,
            reward_id=reward.id,
            status=UserRewardStatus.DELIVERED,
            assigned_by=boss.id,
            idempotency_key=f"test-reward-{next(_ids)}",
        )
    )
    await db.commit()
    return {"boss": boss, "member": member}


async def test_finance_counts_only_confirmed_income(db: AsyncSession) -> None:
    await _data(db)
    doc = await documents.finance(db, documents.Params())
    summary = doc.tables[0]
    pairs = {row[0]: row[1] for row in summary.rows}
    assert "50 000" in pairs["Karta orqali (so'm)"].replace("\xa0", " ")  # the approved one only
    assert "999" not in pairs["Karta orqali (so'm)"]  # the pending one is excluded
    assert pairs["Telegram Stars"] == "100 ⭐"
    # the detailed rows: one card payment + one Stars payment
    records = doc.tables[1].rows
    assert len(records) == 2


async def test_rewards_log_lists_what_was_given(db: AsyncSession) -> None:
    await _data(db)
    doc = await documents.rewards_log(db, documents.Params())
    rows = doc.tables[0].rows
    assert len(rows) == 1
    assert "Bepul Premium" in rows[0][4] and rows[0][5] == "yetkazildi"


@pytest.mark.parametrize("code", ["finance", "rewards_log"])
async def test_both_download_as_excel(client: httpx.AsyncClient, db: AsyncSession, code: str) -> None:
    people = await _data(db)
    response = await client.get(
        f"/api/v1/admin/documents/{code}/file?format=xlsx", headers=admin_headers(people["boss"])
    )
    assert response.status_code == 200 and len(response.content) > 0
