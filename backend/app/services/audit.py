"""Audit trail of important actions (admin login, permission changes, score corrections, ...)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import client_ip_ctx, request_id_ctx
from app.models import AuditLog, User


def record_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditLog:
    """Add an audit record to the current transaction (it is committed together with the change)."""
    entry = AuditLog(
        actor_user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before,
        after=after,
        reason=reason,
        ip_address=client_ip_ctx.get(),
        request_id=request_id_ctx.get(),
    )
    session.add(entry)
    return entry


async def list_audit_logs(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    """Newest first. Returns (rows with the actor's display name, total count)."""
    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id:
        conditions.append(AuditLog.entity_id == entity_id)
    if actor_id:
        conditions.append(AuditLog.actor_user_id == actor_id)
    if since:
        conditions.append(AuditLog.created_at >= since)
    if until:
        conditions.append(AuditLog.created_at < until)

    total = await session.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    actor_name = func.concat(User.first_name, " ", User.last_name)
    rows = await session.execute(
        select(AuditLog, actor_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(log, name) for log, name in rows], int(total or 0)
