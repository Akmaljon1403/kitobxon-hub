"""Public list of active faculties (used by profile forms)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.user import FacultyOut
from app.services.members import list_active_faculties

router = APIRouter(prefix="/faculties", tags=["faculties"])


@router.get("", response_model=list[FacultyOut], summary="Active faculties")
async def faculties(db: DbSession) -> list[FacultyOut]:
    return [FacultyOut(id=f.id, name=f.name, short_name=f.short_name) for f in await list_active_faculties(db)]
