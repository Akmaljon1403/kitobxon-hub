"""Admin Panel: certificates (list, issue by hand, revoke, download)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.api.v1.endpoints.my_documents import certificate_out, file_response
from app.models import Certificate, User
from app.models.enums import CertificateKind
from app.schemas.certificate import AdminCertificateOut, CertificateIssueIn, CertificateMemberOut
from app.schemas.common import Page, ReasonIn
from app.security.permissions import Perm
from app.services import certificates as certificate_service
from app.services.passport import member_number

router = APIRouter(prefix="/admin/certificates", tags=["admin: certificates"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.REWARD_MANAGE))]


def _out(certificate: Certificate, user: User) -> AdminCertificateOut:
    return AdminCertificateOut(
        **certificate_out(certificate).model_dump(),
        member=CertificateMemberOut(
            user_id=user.id, first_name=user.first_name, last_name=user.last_name, member_number=member_number(user)
        ),
        revoked_at=certificate.revoked_at,
        revoke_reason=certificate.revoke_reason,
    )


@router.get("", response_model=Page[AdminCertificateOut], summary="Issued certificates, newest first")
async def list_certificates(
    _: Manager,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    kind: CertificateKind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminCertificateOut]:
    rows, total = await certificate_service.list_admin(db, q=q, kind=kind, limit=limit, offset=offset)
    return Page(items=[_out(c, u) for c, u in rows], total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=AdminCertificateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a certificate by hand (the bot sends it to the member)",
)
async def issue(payload: CertificateIssueIn, current: Manager, db: DbSession) -> AdminCertificateOut:
    certificate = await certificate_service.issue_manual(
        db,
        actor_id=current.user.id,
        user_id=payload.user_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        place=payload.place,
    )
    user = await db.get(User, certificate.user_id)
    assert user is not None
    return _out(certificate, user)


@router.post("/{certificate_id}/revoke", response_model=AdminCertificateOut, summary="Revoke (reason required)")
async def revoke(certificate_id: uuid.UUID, payload: ReasonIn, current: Manager, db: DbSession) -> AdminCertificateOut:
    certificate = await certificate_service.revoke(
        db, actor_id=current.user.id, certificate_id=certificate_id, reason=payload.reason
    )
    user = await db.get(User, certificate.user_id)
    assert user is not None
    return _out(certificate, user)


@router.get("/{certificate_id}/pdf", summary="Download the PDF", response_class=Response)
async def pdf(certificate_id: uuid.UUID, _: Manager, db: DbSession) -> Response:
    certificate = await certificate_service.get(db, certificate_id)
    data = await certificate_service.pdf_bytes(db, certificate)
    await db.commit()
    return file_response(data, "application/pdf", certificate_service.filename(certificate), attachment=True)
