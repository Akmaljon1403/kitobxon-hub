"""The member's documents: the Kitobxon passport image and certificates (PDF)."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, CurrentUserDep, DbSession, get_current_user
from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.models import Certificate
from app.schemas.certificate import CertificateOut, DownloadLinkIn, DownloadLinkOut
from app.security.rate_limit import RateLimit, enforce
from app.services import certificates as certificate_service
from app.services import delivery, downloads
from app.services import passport as passport_service

router = APIRouter(prefix="/me", tags=["me: passport & certificates"])

# Drawing images and PDFs costs CPU; nobody needs more than a few per minute.
FILE_LIMIT = RateLimit("member-files", limit=20, window_seconds=60)
SEND_LIMIT = RateLimit("member-files-send", limit=6, window_seconds=60)


async def _file_limit(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    await enforce(FILE_LIMIT, str(current.user.id))
    return current


async def _send_limit(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    await enforce(SEND_LIMIT, str(current.user.id))
    return current


FileUser = Annotated[CurrentUser, Depends(_file_limit)]
SendUser = Annotated[CurrentUser, Depends(_send_limit)]


def file_response(content: bytes, media_type: str, filename: str, *, attachment: bool) -> Response:
    disposition = "attachment" if attachment else "inline"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}"},
    )


def certificate_out(certificate: Certificate) -> CertificateOut:
    return CertificateOut(
        id=certificate.id,
        kind=certificate.kind,
        place=certificate.place,
        title=certificate.title,
        description=certificate.description,
        issued_at=certificate.issued_at,
        code=certificate_service.display_code(certificate.verify_code),
    )


@router.get("/passport", summary="My Kitobxon passport (PNG image)", response_class=Response)
async def passport_image(current: FileUser, db: DbSession, download: bool = False) -> Response:
    image = await passport_service.render(db, current.user, bot=delivery.optional_bot())
    return file_response(image, "image/png", passport_service.filename(current.user), attachment=download)


@router.post("/passport/send", status_code=status.HTTP_204_NO_CONTENT, summary="The bot sends me my passport")
async def send_passport(current: SendUser, db: DbSession) -> Response:
    await delivery.explain_failures(delivery.send_passport(delivery.runtime_bot(), db, current.user, as_file=True))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/certificates", response_model=list[CertificateOut], summary="My certificates")
async def my_certificates(current: CurrentUserDep, db: DbSession) -> list[CertificateOut]:
    return [certificate_out(c) for c in await certificate_service.member_certificates(db, current.user.id)]


@router.get("/certificates/{certificate_id}/pdf", summary="Download a certificate (PDF)", response_class=Response)
async def certificate_pdf(certificate_id: uuid.UUID, current: FileUser, db: DbSession) -> Response:
    certificate = await certificate_service.get_own(db, user_id=current.user.id, certificate_id=certificate_id)
    data = await certificate_service.pdf_bytes(db, certificate)
    await db.commit()  # remembers where the PDF is stored
    return file_response(data, "application/pdf", certificate_service.filename(certificate), attachment=True)


@router.post(
    "/certificates/{certificate_id}/send",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="The bot sends me a certificate (PDF)",
)
async def send_certificate(certificate_id: uuid.UUID, current: SendUser, db: DbSession) -> Response:
    certificate = await certificate_service.get_own(db, user_id=current.user.id, certificate_id=certificate_id)
    await delivery.explain_failures(delivery.send_certificate(delivery.runtime_bot(), db, current.user, certificate))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/downloads", response_model=DownloadLinkOut, summary="A 5-minute link for Telegram's file download")
async def download_link(payload: DownloadLinkIn, current: CurrentUserDep, db: DbSession) -> DownloadLinkOut:
    base = get_settings().base_url
    if not base:
        raise ServiceUnavailableError(
            "NO_PUBLIC_URL", "Yuklab olish havolasi sozlanmagan. «Botga yuborish»dan foydalaning."
        )
    if payload.kind == "passport":
        token = downloads.make_token("passport", current.user.id)
        name = passport_service.filename(current.user)
    else:
        certificate = await certificate_service.get_own(
            db, user_id=current.user.id, certificate_id=payload.id or uuid.UUID(int=0)
        )
        token = downloads.make_token("certificate", certificate.id)
        name = certificate_service.filename(certificate)
    return DownloadLinkOut(url=f"{base}/api/v1/files/{token}", filename=name, expires_in=downloads.TTL_SECONDS)
