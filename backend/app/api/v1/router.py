"""Version 1 of the public REST API (mounted at ``/api/v1``)."""

from fastapi import APIRouter

from app.api.v1.endpoints import meta

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meta.router)
