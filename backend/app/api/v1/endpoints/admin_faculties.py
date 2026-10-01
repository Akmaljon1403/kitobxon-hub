"""Admin Panel: faculty list (deactivate instead of delete, so member data stays consistent)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentAdminDep, CurrentUser, DbSession, require_permissions
from app.models import Faculty
from app.schemas.faculty import FacultyAdminOut, FacultyIn, FacultyUpdateIn
from app.security.permissions import Perm
from app.services import faculties as faculty_service

router = APIRouter(prefix="/admin/faculties", tags=["admin: faculties"])
SettingsManager = Annotated[CurrentUser, Depends(require_permissions(Perm.SETTINGS_MANAGE))]


def _out(faculty: Faculty) -> FacultyAdminOut:
    return FacultyAdminOut(
        id=faculty.id,
        name=faculty.name,
        short_name=faculty.short_name,
        is_active=faculty.is_active,
        sort_order=faculty.sort_order,
    )


@router.get("", response_model=list[FacultyAdminOut], summary="All faculties")
async def list_faculties(_: CurrentAdminDep, db: DbSession) -> list[FacultyAdminOut]:
    return [_out(item) for item in await faculty_service.list_faculties(db)]


@router.post("", response_model=FacultyAdminOut, status_code=status.HTTP_201_CREATED, summary="Add a faculty")
async def create_faculty(payload: FacultyIn, current: SettingsManager, db: DbSession) -> FacultyAdminOut:
    faculty = await faculty_service.create_faculty(db, actor_id=current.user.id, **payload.model_dump())
    return _out(faculty)


@router.patch("/{faculty_id}", response_model=FacultyAdminOut, summary="Rename, reorder or (de)activate a faculty")
async def update_faculty(
    faculty_id: uuid.UUID, payload: FacultyUpdateIn, current: SettingsManager, db: DbSession
) -> FacultyAdminOut:
    faculty = await faculty_service.update_faculty(
        db, actor_id=current.user.id, faculty_id=faculty_id, **payload.model_dump()
    )
    return _out(faculty)
