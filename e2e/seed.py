"""Seed data for the browser end-to-end tests.

Run from the ``backend`` folder after ``alembic upgrade head``, with the same environment
variables as the server under test. Creates a super admin and a registered member (the bot
registration conversation is covered by the backend tests), signs Telegram launch data for the
member and for a stranger, issues one-time Admin Panel links, and writes ``e2e/.state.json``.
Everything else (book, event, test) is created by the tests through the real admin API.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import Faculty, Role, User, UserRole
from app.models.enums import UserStatus
from app.security.telegram import sign_init_data
from app.services.auth import create_admin_login_link
from app.services.bootstrap import sync_reference_data

ADMIN_TELEGRAM_ID = 7_009_009
MEMBER_TELEGRAM_ID = 7_001_001
STRANGER_TELEGRAM_ID = 7_005_005
STATE = Path(__file__).resolve().parent / ".state.json"


def init_data(telegram_id: int, first_name: str) -> str:
    user = json.dumps({"id": telegram_id, "first_name": first_name, "language_code": "uz"}, separators=(",", ":"))
    fields = {"query_id": "E2E", "user": user, "auth_date": str(int(time.time()))}
    token = get_settings().bot_token
    assert token is not None, "BOT_TOKEN must be set"
    fields["hash"] = sign_init_data(fields, token.get_secret_value())
    return urlencode(fields)


async def main() -> None:
    async with get_session_factory()() as session:
        await sync_reference_data(session)
        faculty = await session.scalar(select(Faculty).order_by(Faculty.sort_order).limit(1))
        now = datetime.now(UTC)
        admin = User(
            telegram_id=ADMIN_TELEGRAM_ID,
            first_name="Akmal",
            last_name="Sinovchi",
            status=UserStatus.ACTIVE,
            registered_at=now,
        )
        member = User(
            telegram_id=MEMBER_TELEGRAM_ID,
            first_name="Madina",
            last_name="Kitobxonova",
            phone="+998901112233",
            faculty_id=faculty.id if faculty else None,
            course=2,
            group_name="201",
            status=UserStatus.ACTIVE,
            registered_at=now,
        )
        session.add_all([admin, member])
        await session.flush()
        role = await session.scalar(select(Role).where(Role.code == "SUPER_ADMIN"))
        session.add(UserRole(user_id=admin.id, role_id=role.id))
        await session.commit()
        api_link, _ = await create_admin_login_link(session, admin)
        ui_link, _ = await create_admin_login_link(session, admin)
    state = {
        "member": {
            "init_data": init_data(MEMBER_TELEGRAM_ID, "Madina"),
            "first_name": "Madina",
            "last_name": "Kitobxonova",
        },
        "stranger_init_data": init_data(STRANGER_TELEGRAM_ID, "Mehmon"),
        "admin_links": {"api": api_link, "ui": ui_link},
    }
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"E2E seed written to {STATE}")


if __name__ == "__main__":
    asyncio.run(main())
