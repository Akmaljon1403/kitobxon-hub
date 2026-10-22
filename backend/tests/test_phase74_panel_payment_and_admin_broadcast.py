"""Two owner requests, verified together:

* Q5 — payment conversations show up in the Admin Panel «Murojaatlar» for the admins allowed to see
  money questions (they still go to the payments channel too); a general-only admin never sees them.
* Q6 — «📢 Xabarlar» can target the administrators («Adminlarga»): the message reaches every admin and
  no ordinary member.
"""

from __future__ import annotations

import itertools

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, User
from app.security.permissions import Perm
from app.services import announcements, support
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

_ids = itertools.count(7_400_000)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _people(db: AsyncSession) -> dict[str, User]:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmal", last_name="Bosh")
    helper = await create_user(db, telegram_id=next(_ids), first_name="Dilnoza", last_name="Aliyeva")
    member = await create_user(db, telegram_id=next(_ids), first_name="Nodir", last_name="Qodirov")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await grant_role(db, helper, "ADMIN")
    await grant_permissions(db, helper, Perm.SUPPORT_MANAGE)
    await grant_permissions(db, boss, Perm.NOTIFICATION_SEND)
    return {"boss": boss, "helper": helper, "member": member}


# ---------------------------------------------------------------------------- Q5


async def test_panel_lists_payment_for_a_permitted_admin(client: httpx.AsyncClient, db: AsyncSession) -> None:
    people = await _people(db)
    payment = await support.member_message(db, user=people["member"], text="Chek yubordim", topic="payment")
    general = await support.member_message(db, user=people["member"], text="Oddiy savol")
    await db.commit()

    # The super admin (holds «💳 To'lov savollari») sees BOTH kinds in the panel.
    boss_headers = admin_headers(people["boss"])
    both = (await client.get("/api/v1/admin/support?limit=50", headers=boss_headers)).json()
    ids = {row["id"] for row in both["items"]}
    assert str(general.id) in ids and str(payment.id) in ids

    # …and can narrow to money questions only.
    only_pay = (await client.get("/api/v1/admin/support?kind=PAYMENT", headers=boss_headers)).json()
    pay_ids = {row["id"] for row in only_pay["items"]}
    assert pay_ids == {str(payment.id)}
    assert only_pay["items"][0]["kind"] == "PAYMENT"

    # A general-only admin still never sees the payment one, and may not ask for it.
    helper_headers = admin_headers(people["helper"])
    general_only = (await client.get("/api/v1/admin/support?limit=50", headers=helper_headers)).json()
    helper_ids = {row["id"] for row in general_only["items"]}
    assert str(general.id) in helper_ids and str(payment.id) not in helper_ids
    denied = await client.get("/api/v1/admin/support?kind=PAYMENT", headers=helper_headers)
    assert denied.status_code == 403


# ---------------------------------------------------------------------------- Q6


async def test_broadcast_to_admins_reaches_admins_only(client: httpx.AsyncClient, db: AsyncSession) -> None:
    people = await _people(db)
    extra_member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    admins = {people["boss"].id, people["helper"].id}
    everyone = admins | {people["member"].id, extra_member.id}

    # Counts: «Adminlarga» is only the administrators; a normal broadcast is every active member.
    boss_id = people["boss"].id
    admin_count = await announcements.broadcast(db, actor_id=boss_id, message="Son", to_admins=True, dry_run=True)
    all_count = await announcements.broadcast(db, actor_id=boss_id, message="Son", dry_run=True)
    assert admin_count == len(admins)
    assert all_count == len(everyone)

    # A real «Adminlarga» send queues a message for every admin and for no ordinary member.
    sent = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"message": "Adminlarga maxfiy eslatma", "to_admins": True},
        headers=admin_headers(people["boss"]),
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["recipients"] == len(admins)

    recipients = set(await db.scalars(select(Notification.user_id).where(Notification.dedup_key.like("broadcast:%"))))
    assert recipients == admins
    assert people["member"].id not in recipients and extra_member.id not in recipients
