"""Admin Panel: certificates (list, issue by hand or as a gift, revoke, download) and the visual designer."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.api.v1.endpoints.my_documents import certificate_out, file_response
from app.models import Certificate, CertificateTemplate, User
from app.models.enums import CertificateKind
from app.schemas.certificate import (
    AdminCertificateOut,
    CertificateIssueIn,
    CertificateMemberOut,
    TemplateElement,
    TemplateOut,
    TemplateUpsertIn,
)
from app.schemas.common import Page, ReasonIn
from app.security.permissions import Perm
from app.services import certificate_templates as templates
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
    summary="Issue a certificate by hand (optionally with a design and a personal gift message)",
)
async def issue(payload: CertificateIssueIn, current: Manager, db: DbSession) -> AdminCertificateOut:
    message = payload.message.strip() if payload.message else None
    certificate = await certificate_service.issue_manual(
        db,
        actor_id=current.user.id,
        user_id=payload.user_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        place=payload.place,
        template_id=payload.template_id,
        gift_message=message or None,
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


# ---------------------------------------------------------------------------- the visual designer


templates_router = APIRouter(prefix="/admin/certificate-templates", tags=["admin: certificate designer"])
Designer = Annotated[CurrentUser, Depends(require_permissions(Perm.REWARD_MANAGE))]


def _template_out(template: CertificateTemplate) -> TemplateOut:
    elements = [TemplateElement.model_validate(item) for item in (template.elements or []) if _valid(item)]
    return TemplateOut(
        id=template.id,
        name=template.name,
        has_background=bool(template.background_key),
        bg_width=template.bg_width,
        bg_height=template.bg_height,
        elements=elements,
        is_default=template.is_default,
        updated_at=template.updated_at,
    )


def _valid(item: object) -> bool:
    try:
        TemplateElement.model_validate(item)
        return True
    except Exception:
        return False


@templates_router.get("", response_model=list[TemplateOut], summary="All certificate designs")
async def list_templates(_: Designer, db: DbSession) -> list[TemplateOut]:
    return [_template_out(template) for template in await templates.list_templates(db)]


@templates_router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED, summary="New design")
async def create_template(payload: TemplateUpsertIn, current: Designer, db: DbSession) -> TemplateOut:
    template = await templates.create(
        db,
        actor_id=current.user.id,
        name=templates.guard_name(payload.name),
        elements=payload.elements,
        is_default=payload.is_default,
    )
    return _template_out(template)


@templates_router.get("/{template_id}", response_model=TemplateOut, summary="One design")
async def get_template(template_id: uuid.UUID, _: Designer, db: DbSession) -> TemplateOut:
    return _template_out(await templates.get(db, template_id))


@templates_router.put("/{template_id}", response_model=TemplateOut, summary="Save the design")
async def update_template(
    template_id: uuid.UUID, payload: TemplateUpsertIn, current: Designer, db: DbSession
) -> TemplateOut:
    template = await templates.get(db, template_id)
    template = await templates.update(
        db,
        actor_id=current.user.id,
        template=template,
        name=templates.guard_name(payload.name),
        elements=payload.elements,
        is_default=payload.is_default,
    )
    return _template_out(template)


@templates_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove the design")
async def delete_template(template_id: uuid.UUID, current: Designer, db: DbSession) -> Response:
    template = await templates.get(db, template_id)
    await templates.delete(db, actor_id=current.user.id, template=template)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@templates_router.put(
    "/{template_id}/background", response_model=TemplateOut, summary="Upload the design picture (PNG, JPG or PDF)"
)
async def upload_background(
    template_id: uuid.UUID, current: Designer, db: DbSession, file: Annotated[UploadFile, File()]
) -> TemplateOut:
    template = await templates.get(db, template_id)
    data = await file.read(templates.MAX_BYTES + 1)
    await templates.set_background(db, template=template, actor_id=current.user.id, data=data)
    return _template_out(template)


@templates_router.get("/{template_id}/background", summary="The uploaded picture", response_class=Response)
async def background(template_id: uuid.UUID, _: Designer, db: DbSession) -> Response:
    template = await templates.get(db, template_id)
    data = await templates.background_bytes(template)
    return Response(content=data, media_type="image/png")


@templates_router.get(
    "/{template_id}/preview.png", summary="A sample certificate on this design", response_class=Response
)
async def preview(template_id: uuid.UUID, _: Designer, db: DbSession) -> Response:
    template = await templates.get(db, template_id)
    image = await templates.preview_png(db, template)
    return Response(content=image, media_type="image/png", headers={"Cache-Control": "no-store"})
