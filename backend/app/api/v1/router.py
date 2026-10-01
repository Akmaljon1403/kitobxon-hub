"""Version 1 of the public REST API (mounted at ``/api/v1``)."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_access,
    admin_books,
    admin_events,
    admin_faculties,
    admin_notifications,
    admin_quizzes,
    admin_scores,
    admin_system,
    admin_users,
    auth,
    books,
    events,
    faculties,
    me,
    meta,
    quizzes,
    scores,
)

api_router = APIRouter(prefix="/api/v1")
for module in (
    meta,
    auth,
    me,
    faculties,
    books,
    events,
    quizzes,
    scores,
    admin_access,
    admin_users,
    admin_books,
    admin_events,
    admin_faculties,
    admin_quizzes,
    admin_scores,
    admin_notifications,
    admin_system,
):
    api_router.include_router(module.router)
