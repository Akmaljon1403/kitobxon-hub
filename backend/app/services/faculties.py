"""Faculty list management (used by registration and faculty rankings)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import Faculty
from app.services.audit import record_audit


def _snapshot(faculty: Faculty) -> dict:
    return {
        "name": faculty.name,
        "short_name": faculty.short_name,
        "is_active": faculty.is_active,
        "sort_order": faculty.sort_order,
    }


async def list_faculties(session: AsyncSession) -> list[Faculty]:
    return list(await session.scalars(select(Faculty).order_by(Faculty.sort_order, Faculty.name)))


async def create_faculty(
    session: AsyncSession, *, actor_id: uuid.UUID, name: str, short_name: str | None, sort_order: int, is_active: bool
) -> Faculty:
    faculty = Faculty(name=name.strip(), short_name=short_name, sort_order=sort_order, is_active=is_active)
    session.add(faculty)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("FACULTY_EXISTS", "Bunday nomli fakultet allaqachon mavjud.") from exc
    record_audit(
        session,
        actor_id=actor_id,
        action="FACULTY_CREATE",
        entity_type="faculty",
        entity_id=faculty.id,
        after=_snapshot(faculty),
    )
    await session.commit()
    return faculty


async def update_faculty(session: AsyncSession, *, actor_id: uuid.UUID, faculty_id: uuid.UUID, **changes) -> Faculty:
    faculty = await session.get(Faculty, faculty_id)
    if faculty is None:
        raise NotFoundError("FACULTY_NOT_FOUND", "Fakultet topilmadi.")
    before = _snapshot(faculty)
    for field, value in changes.items():
        if value is not None:
            setattr(faculty, field, value.strip() if isinstance(value, str) else value)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("FACULTY_EXISTS", "Bunday nomli fakultet allaqachon mavjud.") from exc
    record_audit(
        session,
        actor_id=actor_id,
        action="FACULTY_UPDATE",
        entity_type="faculty",
        entity_id=faculty.id,
        before=before,
        after=_snapshot(faculty),
    )
    await session.commit()
    return faculty
