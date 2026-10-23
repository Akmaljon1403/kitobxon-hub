"""Phases 8-9: profiles, member administration, settings, statistics, books, reading and quotes."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, BookQuote, Faculty, Notification, ScoreTransaction, SystemSetting, User
from app.models.enums import QuoteStatus, ScoreCategory, UserStatus
from app.security.permissions import Perm
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


async def _admin(db: AsyncSession, *permissions: Perm, role: str = "ADMIN") -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, role)
    if permissions:
        await grant_permissions(db, user, *permissions)
    return user


async def _faculty(db: AsyncSession, name: str) -> Faculty:
    faculty = Faculty(name=name)
    db.add(faculty)
    await db.commit()
    return faculty


# ---------------------------------------------------------------------------- profile


async def test_public_faculty_list(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await _faculty(db, "Pediatriya")
    hidden = await _faculty(db, "Eski fakultet")
    hidden.is_active = False
    await db.commit()
    response = await client.get("/api/v1/faculties")
    assert [item["name"] for item in response.json()] == ["Pediatriya"]


async def test_member_updates_own_study_details(client: httpx.AsyncClient, db: AsyncSession) -> None:
    faculty = await _faculty(db, "Davolash ishi")
    member = await create_user(db, course=1, group_name="101")
    await db.commit()
    headers = member_headers(member)

    response = await client.patch(
        "/api/v1/me",
        json={"faculty_id": str(faculty.id), "course": 2, "group_name": "201-b", "first_name": "Hacker"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["faculty"]["name"] == "Davolash ishi"
    assert (body["course"], body["group_name"]) == (2, "201-B")
    assert body["first_name"] != "Hacker"  # names are changed only by admins
    assert body["max_course"] == 6

    too_high = await client.patch("/api/v1/me", json={"course": 7}, headers=headers)
    assert too_high.status_code == 422
    assert too_high.json()["error"]["code"] == "INVALID_COURSE"


async def test_notification_settings_api(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    headers = member_headers(member)
    initial = await client.get("/api/v1/me/notification-settings", headers=headers)
    assert initial.json()["quote_of_day"] is True
    updated = await client.put("/api/v1/me/notification-settings", json={"quote_of_day": False}, headers=headers)
    assert updated.json()["quote_of_day"] is False
    assert updated.json()["event_reminders"] is True


# ---------------------------------------------------------------------------- member administration


async def test_member_search_hides_phone_without_permission(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await create_user(db, first_name="Dilnoza", last_name="Karimova", phone="+998901112233")
    await create_user(db, first_name="Jasur", last_name="Aliyev")
    viewer = await _admin(db, Perm.USER_VIEW)
    contact_viewer = await _admin(db, Perm.USER_VIEW, Perm.USER_CONTACT_VIEW)

    found = await client.get("/api/v1/admin/users?search=karim", headers=admin_headers(viewer))
    assert found.status_code == 200
    assert found.json()["total"] == 1
    assert found.json()["items"][0]["phone"] is None

    with_phone = await client.get("/api/v1/admin/users?search=karim", headers=admin_headers(contact_viewer))
    assert with_phone.json()["items"][0]["phone"] == "+998901112233"

    # Searching by phone number is only possible with the contact permission.
    assert (await client.get("/api/v1/admin/users?search=1112233", headers=admin_headers(viewer))).json()["total"] == 0
    by_phone = await client.get("/api/v1/admin/users?search=1112233", headers=admin_headers(contact_viewer))
    assert by_phone.json()["total"] == 1


async def test_search_wildcards_are_literal(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await create_user(db, first_name="Ali")
    viewer = await _admin(db, Perm.USER_VIEW)
    response = await client.get("/api/v1/admin/users?search=%25", headers=admin_headers(viewer))
    assert response.json()["total"] == 0


async def test_admin_corrects_member_data_with_audit(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, first_name="Alli")
    manager = await _admin(db, Perm.USER_VIEW, Perm.USER_MANAGE)
    response = await client.patch(
        f"/api/v1/admin/users/{member.id}", json={"first_name": "Ali"}, headers=admin_headers(manager)
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Ali"
    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "USER_UPDATE"))
    assert entry.before["first_name"] == "Alli" and entry.after["first_name"] == "Ali"


async def test_view_only_admin_cannot_change_members(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    viewer = await _admin(db, Perm.USER_VIEW)
    response = await client.patch(
        f"/api/v1/admin/users/{member.id}", json={"first_name": "Ali"}, headers=admin_headers(viewer)
    )
    assert response.status_code == 403


async def test_blocking_member(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    manager = await _admin(db, Perm.USER_VIEW, Perm.USER_MANAGE)
    member_session = member_headers(member)

    no_reason = await client.post(
        f"/api/v1/admin/users/{member.id}/status", json={"status": "BLOCKED"}, headers=admin_headers(manager)
    )
    assert no_reason.status_code == 422

    blocked = await client.post(
        f"/api/v1/admin/users/{member.id}/status",
        json={"status": "BLOCKED", "reason": "Qoidalarni qo'pol buzdi"},
        headers=admin_headers(manager),
    )
    assert blocked.json()["status"] == "BLOCKED"
    assert (await client.get("/api/v1/me", headers=member_session)).status_code == 401
    assert await db.scalar(select(AuditLog.reason).where(AuditLog.action == "USER_BLOCK")) == "Qoidalarni qo'pol buzdi"


async def test_approving_pending_member_queues_message(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, status=UserStatus.PENDING)
    manager = await _admin(db, Perm.USER_VIEW, Perm.USER_MANAGE)
    response = await client.post(
        f"/api/v1/admin/users/{member.id}/status",
        json={"status": "ACTIVE", "reason": "Klub a'zosi ekani tasdiqlandi"},
        headers=admin_headers(manager),
    )
    assert response.json()["status"] == "ACTIVE"
    notification = await db.scalar(select(Notification).where(Notification.user_id == member.id))
    assert notification is not None and "tasdiqlandi" in notification.text


async def test_admins_are_protected_from_other_admins(client: httpx.AsyncClient, db: AsyncSession) -> None:
    manager = await _admin(db, Perm.USER_VIEW, Perm.USER_MANAGE)
    other_admin = await _admin(db)
    response = await client.post(
        f"/api/v1/admin/users/{other_admin.id}/status",
        json={"status": "BLOCKED", "reason": "Sinov uchun bloklash"},
        headers=admin_headers(manager),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_PROTECTED"

    self_block = await client.post(
        f"/api/v1/admin/users/{manager.id}/status",
        json={"status": "BLOCKED", "reason": "Sinov uchun bloklash"},
        headers=admin_headers(manager),
    )
    assert self_block.json()["error"]["code"] == "SELF_STATUS_CHANGE"


# ---------------------------------------------------------------------------- settings and statistics


async def test_settings_are_typed_and_audited(client: httpx.AsyncClient, db: AsyncSession) -> None:
    plain_admin = await _admin(db)
    manager = await _admin(db, Perm.SETTINGS_MANAGE)

    listing = await client.get("/api/v1/admin/settings", headers=admin_headers(plain_admin))
    assert listing.status_code == 200
    by_key = {item["key"]: item for item in listing.json()}
    assert by_key["score.attendance_points"]["value"] == 30
    assert by_key["score.attendance_points"]["kind"] == "int"
    assert by_key["ranking.public_name_format"]["choices"] == ["FULL", "SHORT"]

    denied = await client.put(
        "/api/v1/admin/settings/score.attendance_points", json={"value": 40}, headers=admin_headers(plain_admin)
    )
    assert denied.status_code == 403

    invalid = await client.put(
        "/api/v1/admin/settings/score.attendance_points", json={"value": -5}, headers=admin_headers(manager)
    )
    assert invalid.status_code == 422

    unknown = await client.put("/api/v1/admin/settings/no.such.key", json={"value": 1}, headers=admin_headers(manager))
    assert unknown.status_code == 404

    changed = await client.put(
        "/api/v1/admin/settings/score.attendance_points", json={"value": 40}, headers=admin_headers(manager)
    )
    assert changed.json()["value"] == 40
    assert (await db.get(SystemSetting, "score.attendance_points")).value == 40
    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "SETTING_CHANGE"))
    assert entry.before == {"value": 30} and entry.after == {"value": 40}


async def test_dashboard_statistics(client: httpx.AsyncClient, db: AsyncSession) -> None:
    faculty = await _faculty(db, "Pediatriya")
    await create_user(db, faculty_id=faculty.id)
    await create_user(db, status=UserStatus.PENDING)
    analyst = await _admin(db, Perm.ANALYTICS_VIEW)
    response = await client.get("/api/v1/admin/statistics", headers=admin_headers(analyst))
    assert response.status_code == 200
    body = response.json()
    assert body["users"]["total"] == 3
    assert body["users"]["pending"] == 1
    assert {"name": "Pediatriya", "members": 1} in body["faculties"]


# ---------------------------------------------------------------------------- books


BOOK = {
    "title": "O'tkan kunlar",
    "author": "Abdulla Qodiriy",
    "description": "O'zbek adabiyotining birinchi romani.",
    "cover_url": "https://example.org/cover.jpg",
    "source_url": "https://example.org/otkan-kunlar",
    "pages": 384,
    "start_date": str(date.today()),
    "deadline": str(date.today() + timedelta(days=14)),
}


async def _published_book(client: httpx.AsyncClient, admin: User) -> str:
    created = await client.post("/api/v1/admin/books", json=BOOK, headers=admin_headers(admin))
    assert created.status_code == 201, created.text
    book_id = created.json()["id"]
    published = await client.patch(
        f"/api/v1/admin/books/{book_id}", json={"status": "ACTIVE"}, headers=admin_headers(admin)
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "ACTIVE"
    return book_id


async def test_book_lifecycle_and_visibility(client: httpx.AsyncClient, db: AsyncSession) -> None:
    editor = await _admin(db, Perm.BOOK_VIEW, Perm.BOOK_CREATE, Perm.BOOK_EDIT, Perm.BOOK_DELETE)
    member = await create_user(db)
    await db.commit()

    created = await client.post("/api/v1/admin/books", json=BOOK, headers=admin_headers(editor))
    book_id = created.json()["id"]
    assert created.json()["status"] == "DRAFT"
    assert (await client.get("/api/v1/books", headers=member_headers(member))).json()["total"] == 0
    assert (await client.get(f"/api/v1/books/{book_id}", headers=member_headers(member))).status_code == 404

    published = await client.patch(
        f"/api/v1/admin/books/{book_id}", json={"status": "ACTIVE"}, headers=admin_headers(editor)
    )
    assert published.status_code == 200, published.text
    listing = await client.get("/api/v1/books", headers=member_headers(member))
    assert listing.json()["items"][0]["title"] == "O'tkan kunlar"
    assert listing.json()["items"][0]["my_reading"] is None

    assert (await client.delete(f"/api/v1/admin/books/{book_id}", headers=admin_headers(editor))).status_code == 204
    assert (await client.get("/api/v1/books", headers=member_headers(member))).json()["total"] == 0
    actions = set(await db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "book")))
    assert {"BOOK_CREATE", "BOOK_UPDATE", "BOOK_DELETE"} <= actions


async def test_book_validation(client: httpx.AsyncClient, db: AsyncSession) -> None:
    creator = await _admin(db, Perm.BOOK_CREATE)
    bad_dates = {**BOOK, "deadline": str(date.today() - timedelta(days=1))}
    assert (await client.post("/api/v1/admin/books", json=bad_dates, headers=admin_headers(creator))).status_code == 422
    bad_url = {**BOOK, "source_url": "javascript:alert(1)"}
    assert (await client.post("/api/v1/admin/books", json=bad_url, headers=admin_headers(creator))).status_code == 422


async def test_book_permissions(client: httpx.AsyncClient, db: AsyncSession) -> None:
    viewer = await _admin(db, Perm.BOOK_VIEW)
    assert (await client.get("/api/v1/admin/books", headers=admin_headers(viewer))).status_code == 200
    assert (await client.post("/api/v1/admin/books", json=BOOK, headers=admin_headers(viewer))).status_code == 403


async def test_reading_requires_verification_for_points(client: httpx.AsyncClient, db: AsyncSession) -> None:
    editor = await _admin(db, Perm.BOOK_VIEW, Perm.BOOK_CREATE, Perm.BOOK_EDIT)
    member = await create_user(db)
    await db.commit()
    book_id = await _published_book(client, editor)
    headers = member_headers(member)

    started = await client.post(f"/api/v1/books/{book_id}/reading", json={"action": "start"}, headers=headers)
    assert started.json()["my_reading"]["status"] == "READING"
    finished = await client.post(f"/api/v1/books/{book_id}/reading", json={"action": "complete"}, headers=headers)
    assert finished.json()["my_reading"]["status"] == "COMPLETED"
    assert finished.json()["my_reading"]["verified"] is False
    assert await db.scalar(select(func.count()).select_from(ScoreTransaction)) == 0  # self-report alone: no points

    readers = await client.get(f"/api/v1/admin/books/{book_id}/readers", headers=admin_headers(editor))
    assert readers.json()[0]["status"] == "COMPLETED"

    for _ in range(2):  # verifying twice must not award twice
        verified = await client.post(
            f"/api/v1/admin/books/{book_id}/readers/{member.id}/verify", headers=admin_headers(editor)
        )
        assert verified.status_code == 204
    rows = (await db.execute(select(ScoreTransaction.amount, ScoreTransaction.category))).all()
    assert rows == [(10, ScoreCategory.BOOK_COMPLETION)]

    detail = await client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert detail.json()["my_reading"]["verified"] is True
    assert detail.json()["completed_count"] == 1


async def test_reading_points_immediately_when_configured(client: httpx.AsyncClient, db: AsyncSession) -> None:
    setting = await db.get(SystemSetting, "score.book_completion_requires_verification")
    setting.value = False
    await db.commit()
    editor = await _admin(db, Perm.BOOK_CREATE, Perm.BOOK_EDIT)
    member = await create_user(db)
    await db.commit()
    book_id = await _published_book(client, editor)
    for _ in range(2):
        await client.post(
            f"/api/v1/books/{book_id}/reading", json={"action": "complete"}, headers=member_headers(member)
        )
    assert await db.scalar(select(func.sum(ScoreTransaction.amount))) == 10


async def test_reading_points_respect_the_deadline(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """A past deadline earns no points; a future (or absent) deadline does."""
    setting = await db.get(SystemSetting, "score.book_completion_requires_verification")
    setting.value = False
    await db.commit()
    editor = await _admin(db, Perm.BOOK_CREATE, Perm.BOOK_EDIT)
    member = await create_user(db)
    await db.commit()

    async def publish(title: str, deadline: str | None, start: str | None) -> str:
        created = await client.post(
            "/api/v1/admin/books",
            json={**BOOK, "title": title, "start_date": start, "deadline": deadline},
            headers=admin_headers(editor),
        )
        assert created.status_code == 201, created.text
        book_id = created.json()["id"]
        await client.patch(f"/api/v1/admin/books/{book_id}", json={"status": "ACTIVE"}, headers=admin_headers(editor))
        return book_id

    # the reading window already closed → finishing now earns no points
    yesterday = str(date.today() - timedelta(days=1))
    past = await publish("Muddati o'tgan", yesterday, str(date.today() - timedelta(days=10)))
    await client.post(f"/api/v1/books/{past}/reading", json={"action": "complete"}, headers=member_headers(member))
    assert await db.scalar(select(func.count()).select_from(ScoreTransaction)) == 0

    # a future deadline → the 10 points are awarded
    future = await publish("Muddati bor", str(date.today() + timedelta(days=7)), str(date.today()))
    await client.post(f"/api/v1/books/{future}/reading", json={"action": "complete"}, headers=member_headers(member))
    assert await db.scalar(select(func.sum(ScoreTransaction.amount))) == 10


async def test_cannot_read_draft_book(client: httpx.AsyncClient, db: AsyncSession) -> None:
    creator = await _admin(db, Perm.BOOK_CREATE)
    member = await create_user(db)
    await db.commit()
    book_id = (await client.post("/api/v1/admin/books", json=BOOK, headers=admin_headers(creator))).json()["id"]
    response = await client.post(
        f"/api/v1/books/{book_id}/reading", json={"action": "start"}, headers=member_headers(member)
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------- quotes


async def test_quotes(client: httpx.AsyncClient, db: AsyncSession) -> None:
    editor = await _admin(db, Perm.BOOK_VIEW, Perm.BOOK_CREATE, Perm.BOOK_EDIT, Perm.BOOK_DELETE)
    member = await create_user(db)
    await db.commit()
    book_id = await _published_book(client, editor)
    today = str(date.today())

    # Q2: administrators no longer author quotes — there is no create endpoint. The quote-of-day queue
    # is fed from members' own quotes; admins only schedule, edit and remove what members contributed.
    # Two such quotes are placed in the queue directly here to exercise those remaining endpoints.
    draft = BookQuote(
        book_id=uuid.UUID(book_id),
        text="Ilm — saodat kalitidir.",
        author="Abdulla Qodiriy",
        source="12-bet",
        status=QuoteStatus.DRAFT,
        created_by=editor.id,
    )
    other = BookQuote(text="Boshqa iqtibos matni", status=QuoteStatus.DRAFT, created_by=editor.id)
    db.add_all([draft, other])
    await db.commit()
    await db.refresh(draft)
    await db.refresh(other)

    # The create endpoint is gone.
    gone = await client.post(
        "/api/v1/admin/quotes",
        json={"book_id": book_id, "text": "Admin yozgan iqtibos"},
        headers=admin_headers(editor),
    )
    assert gone.status_code in (404, 405)

    detail = await client.get(f"/api/v1/books/{book_id}", headers=member_headers(member))
    assert detail.json()["quotes"] == []  # drafts are not shown to members

    scheduled = await client.patch(
        f"/api/v1/admin/quotes/{draft.id}",
        json={"status": "SCHEDULED", "scheduled_date": today},
        headers=admin_headers(editor),
    )
    assert scheduled.json()["status"] == "SCHEDULED"
    detail = await client.get(f"/api/v1/books/{book_id}", headers=member_headers(member))
    assert detail.json()["quotes"][0]["source"] == "12-bet"

    # The same day cannot hold two scheduled quotes.
    clash = await client.patch(
        f"/api/v1/admin/quotes/{other.id}",
        json={"status": "SCHEDULED", "scheduled_date": today},
        headers=admin_headers(editor),
    )
    assert clash.status_code == 400
    assert clash.json()["error"]["code"] == "QUOTE_DATE_TAKEN"

    deleted = await client.delete(f"/api/v1/admin/quotes/{draft.id}", headers=admin_headers(editor))
    assert deleted.status_code == 204
    # The scheduled draft is gone; the other draft remains in the queue.
    assert (await client.get("/api/v1/admin/quotes", headers=admin_headers(editor))).json()["total"] == 1


async def test_member_overview_aggregates_everything(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """Q12: one member's whole picture in a single admin endpoint — points (with breakdown), activity
    counts, support, referrals and premium — reachable with USER_VIEW, and 404 for an unknown member."""
    import uuid

    from app.services.scoring import award_points

    viewer = await _admin(db, Perm.USER_VIEW)
    member = await create_user(db, first_name="Laylo", last_name="Nazarova")
    await db.commit()
    await award_points(db, user_id=member.id, amount=40, category=ScoreCategory.ATTENDANCE, idempotency_key="ov:1")
    await award_points(db, user_id=member.id, amount=10, category=ScoreCategory.TEST, idempotency_key="ov:2")
    await db.commit()

    res = await client.get(f"/api/v1/admin/users/{member.id}/overview", headers=admin_headers(viewer))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["points"]["total"] == 50
    assert body["points"]["breakdown"].get("ATTENDANCE") == 40
    for key in ("attendance", "tests_taken", "books_completed", "support", "referrals", "achievements", "reading"):
        assert key in body
    assert body["support"] == {"total": 0, "open": 0}
    assert body["premium_until"] is None

    missing = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}/overview", headers=admin_headers(viewer))
    assert missing.status_code == 404


async def test_member_score_history_shows_the_reason_for_each_point(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """The admin can see why each point was given to a member (amount, category, reason, who)."""
    from app.services.scoring import award_points

    viewer = await _admin(db, Perm.USER_VIEW)
    member = await create_user(db)
    await db.commit()
    await award_points(
        db,
        user_id=member.id,
        amount=10,
        category=ScoreCategory.CAMPAIGN,
        idempotency_key=f"sh:1:{member.id}",
        reason="A'zolar fikrlari: fikr",
    )
    await award_points(
        db,
        user_id=member.id,
        amount=-3,
        category=ScoreCategory.MANUAL,
        idempotency_key=f"sh:2:{member.id}",
        reason="Admin qo'lda tuzatdi",
        created_by=viewer.id,
    )
    await db.commit()

    res = await client.get(f"/api/v1/admin/users/{member.id}/score-history", headers=admin_headers(viewer))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2
    reasons = {item["reason"] for item in body["items"]}
    assert {"A'zolar fikrlari: fikr", "Admin qo'lda tuzatdi"} <= reasons
    manual = next(item for item in body["items"] if item["category"] == "MANUAL")
    assert manual["amount"] == -3
    assert manual["category_label"] == "Qo'lda tuzatish"
    assert manual["by"]  # the admin who made the correction is named

    missing = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}/score-history", headers=admin_headers(viewer))
    assert missing.status_code == 404
