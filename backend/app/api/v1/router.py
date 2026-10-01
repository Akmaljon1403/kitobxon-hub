"""Version 1 of the public REST API (mounted at ``/api/v1``)."""

from fastapi import APIRouter

from app.api.v1.endpoints import admin_access, auth, me, meta

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(admin_access.router)
