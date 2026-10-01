"""The signed-in member's own data."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSession
from app.models import Faculty
from app.schemas.user import FacultyOut, MeOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut, summary="My profile")
async def get_me(current: CurrentUserDep, db: DbSession) -> MeOut:
    user = current.user
    faculty = await db.get(Faculty, user.faculty_id) if user.faculty_id else None
    return MeOut(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        telegram_username=user.telegram_username,
        photo_url=user.photo_url,
        phone=user.phone,
        faculty=FacultyOut(id=faculty.id, name=faculty.name, short_name=faculty.short_name) if faculty else None,
        course=user.course,
        group_name=user.group_name,
        status=user.status,
        registered_at=user.registered_at,
        is_admin=current.is_admin,
        roles=sorted(current.roles),
    )
