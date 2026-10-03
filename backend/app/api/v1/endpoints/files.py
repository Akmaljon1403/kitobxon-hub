"""Files behind short-lived signed links (made by ``POST /me/downloads``)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import DbSession
from app.api.v1.endpoints.my_documents import file_response
from app.core.errors import NotFoundError
from app.models import User
from app.models.enums import UserStatus
from app.security.rate_limit import RateLimit, limit_by_ip
from app.services import certificates as certificate_service
from app.services import delivery, downloads
from app.services import passport as passport_service

router = APIRouter(prefix="/files", tags=["files"])
LINK_LIMIT = RateLimit("file-links", limit=30, window_seconds=60)


@router.get(
    "/{token}",
    summary="Download a file by a signed link",
    response_class=Response,
    dependencies=[Depends(limit_by_ip(LINK_LIMIT))],
)
async def download(token: str, db: DbSession) -> Response:
    kind, object_id = downloads.read_token(token)
    if kind == "passport":
        user = await db.get(User, object_id)
        if user is None or user.deleted_at is not None or user.status != UserStatus.ACTIVE:
            raise NotFoundError("NOT_FOUND", "Fayl topilmadi.")
        image = await passport_service.render(db, user, bot=delivery.optional_bot())
        return file_response(image, "image/png", passport_service.filename(user), attachment=True)
    if kind == "portfolio":
        from app.services import portfolio

        user = await db.get(User, object_id)
        if user is None or user.deleted_at is not None or user.status != UserStatus.ACTIVE:
            raise NotFoundError("NOT_FOUND", "Fayl topilmadi.")
        data = await portfolio.render_pdf(db, user)
        return file_response(data, "application/pdf", portfolio.filename(user), attachment=True)
    certificate = await certificate_service.get(db, object_id)
    if certificate.revoked_at is not None:
        raise NotFoundError("CERTIFICATE_NOT_FOUND", "Sertifikat topilmadi.")
    data = await certificate_service.pdf_bytes(db, certificate)
    await db.commit()
    return file_response(data, "application/pdf", certificate_service.filename(certificate), attachment=True)
