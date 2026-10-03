"""The member's documents: the Kitobxon passport image and certificates (PDF)."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.api.deps import CurrentUser, CurrentUserDep, DbSession, feature_required, get_current_user
from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.models import Certificate
from app.schemas.certificate import CertificateOut, DownloadLinkIn, DownloadLinkOut, PassportThemeIn, PassportThemeOut
from app.security.rate_limit import RateLimit, enforce
from app.services import certificates as certificate_service
from app.services import delivery, downloads, features
from app.services import passport as passport_service
from app.services import premium as premium_service

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


@router.get(
    "/passport",
    dependencies=[feature_required("passport")],
    summary="My Kitobxon passport (PNG image)",
    response_class=Response,
)
async def passport_image(current: FileUser, db: DbSession, download: bool = False) -> Response:
    image = await passport_service.render(db, current.user, bot=delivery.optional_bot())
    return file_response(image, "image/png", passport_service.filename(current.user), attachment=download)


@router.get("/passport/themes", response_model=list[PassportThemeOut], summary="Card designs (premium)")
async def passport_themes(current: CurrentUserDep, db: DbSession) -> list[PassportThemeOut]:
    premium = await premium_service.is_premium(db, current.user.id)
    chosen = passport_service.effective_theme(current.user.passport_theme, premium)
    return [
        PassportThemeOut(
            code=code,
            title=theme.title,
            premium=theme.premium,
            colors=[f"#{r:02x}{g:02x}{b:02x}" for r, g, b in (theme.dark, theme.light, theme.accent)],
            selected=code == chosen,
        )
        for code, theme in passport_service.THEMES.items()
    ]


@router.put(
    "/passport/theme",
    dependencies=[feature_required("passport")],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Choose the card design (premium members)",
)
async def set_passport_theme(payload: PassportThemeIn, current: CurrentUserDep, db: DbSession) -> Response:
    await passport_service.set_theme(db, current.user, payload.theme)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/passport/photo",
    dependencies=[feature_required("passport")],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Upload my own passport photo (JPG/PNG/WEBP, up to 10 MB)",
)
async def upload_passport_photo(current: FileUser, db: DbSession, file: Annotated[UploadFile, File()]) -> Response:
    data = await file.read(passport_service.MAX_PHOTO_BYTES + 1)
    await passport_service.set_photo(db, current.user, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/passport/photo", status_code=status.HTTP_204_NO_CONTENT, summary="Back to my Telegram profile picture")
async def delete_passport_photo(current: CurrentUserDep, db: DbSession) -> Response:
    await passport_service.clear_photo(db, current.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/passport/send",
    dependencies=[feature_required("passport")],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="The bot sends me my passport",
)
async def send_passport(current: SendUser, db: DbSession) -> Response:
    await delivery.explain_failures(delivery.send_passport(delivery.runtime_bot(), db, current.user, as_file=True))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/certificates",
    dependencies=[feature_required("certificates")],
    response_model=list[CertificateOut],
    summary="My certificates",
)
async def my_certificates(current: CurrentUserDep, db: DbSession) -> list[CertificateOut]:
    return [certificate_out(c) for c in await certificate_service.member_certificates(db, current.user.id)]


@router.get(
    "/certificates/{certificate_id}/pdf",
    dependencies=[feature_required("certificates")],
    summary="Download a certificate (PDF)",
    response_class=Response,
)
async def certificate_pdf(certificate_id: uuid.UUID, current: FileUser, db: DbSession) -> Response:
    certificate = await certificate_service.get_own(db, user_id=current.user.id, certificate_id=certificate_id)
    data = await certificate_service.pdf_bytes(db, certificate)
    await db.commit()  # remembers where the PDF is stored
    return file_response(data, "application/pdf", certificate_service.filename(certificate), attachment=True)


@router.post(
    "/certificates/{certificate_id}/send",
    dependencies=[feature_required("certificates")],
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
    await features.require(db, current.user, payload.kind if payload.kind == "passport" else "certificates")
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
