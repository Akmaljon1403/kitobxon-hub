"""«🛡 Xavfsizlik»: the owners hear at once about the changes that could hurt the club if someone abused a
right — who can manage what, and the settings that move money or speak in the club's name.

Each alert goes to every super admin (priority 1, past the quiet hours), with who did it and when, and stays in
the audit log. A super admin who did it themself is told too — the others need to know.
"""

from __future__ import annotations

import html
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.services import copies
from app.services.notifications import enqueue_for_members

MASKED = ("payments.card_number",)


def _show(key: str, value: Any) -> str:
    text = str(value) if value not in (None, "") else "—"
    if key in MASKED and len(text) > 8:  # enough to recognise, not enough to copy
        digits = "".join(ch for ch in text if ch.isdigit())
        text = f"{digits[:4]} •••• •••• {digits[-4:]}" if len(digits) >= 8 else "••••"
    if len(text) > 120:
        text = text[:117] + "…"
    return html.escape(text, quote=False)


async def _send(session: AsyncSession, text: str, key: str) -> None:
    from app.services.rbac import super_admins

    await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=f"🛡 <b>Xavfsizlik</b>\n\n{text}\n\n<i>{copies.stamp()} · Audit jurnalida ham bor.</i>",
        dedup_prefix=f"security:{key}:{uuid.uuid4().hex[:12]}",
        members=super_admins(),
        payload={"buttons": [{"text": "🧾 Audit jurnali", "admin_route": "audit"}]},
        priority=1,
    )


async def setting_changed(
    session: AsyncSession, *, key: str, actor_id: uuid.UUID | None, before: Any, after: Any
) -> None:
    who = await copies.admin_name(session, actor_id)
    await _send(
        session,
        f"<b>{who}</b> muhim sozlamani o'zgartirdi: <code>{html.escape(key)}</code>\n"
        f"Avval: {_show(key, before)}\nEndi: {_show(key, after)}",
        f"setting:{key}",
    )


async def rights_changed(session: AsyncSession, *, actor_id: uuid.UUID | None, user_id: uuid.UUID, what: str) -> None:
    """An admin appointed or dismissed, given or refused rights."""
    who = await copies.admin_name(session, actor_id)
    whom = await copies.admin_name(session, user_id)
    await _send(session, f"<b>{who}</b> → <b>{whom}</b>: {html.escape(what, quote=False)}", f"rights:{user_id}")
