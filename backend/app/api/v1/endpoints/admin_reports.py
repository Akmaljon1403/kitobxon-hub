"""Admin Panel: official event reports (facts, text, photos, AI or template draft, approval, PDF)."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models import Report, User
from app.models.enums import ReportStatus
from app.schemas.common import Page
from app.schemas.report import (
    GenerateIn,
    ReportCreateIn,
    ReportDetailOut,
    ReportListItem,
    ReportPhotoOut,
    ReportUpdateIn,
)
from app.security.permissions import Perm
from app.services import report_ai, report_pdf
from app.services import reports as report_service
from app.services.storage import get_storage

router = APIRouter(prefix="/admin/reports", tags=["admin: reports"])
Viewer = Annotated[CurrentUser, Depends(require_permissions(Perm.REPORT_VIEW))]
Creator = Annotated[CurrentUser, Depends(require_permissions(Perm.REPORT_VIEW, Perm.REPORT_CREATE))]
Approver = Annotated[CurrentUser, Depends(require_permissions(Perm.REPORT_VIEW, Perm.REPORT_APPROVE))]
PDF_READY = (ReportStatus.PDF_GENERATED, ReportStatus.ARCHIVED)


async def _detail(db, report: Report) -> ReportDetailOut:
    approver = await db.get(User, report.approved_by) if report.approved_by else None
    photos = await report_service.list_photos(db, report.id)
    return ReportDetailOut(
        id=report.id,
        kind=report.kind,
        event_id=report.event_id,
        period_start=report.period_start,
        period_end=report.period_end,
        version=report.version,
        status=report.status,
        title=report.title,
        objective=report.objective,
        activity_description=report.activity_description,
        results=report.results,
        conclusion=report.conclusion,
        recommendations=report.recommendations,
        body_text=report.body_text,
        facts=report.facts_snapshot or {},
        photos=[ReportPhotoOut(id=p.id, caption=p.caption, size_bytes=p.size_bytes) for p in photos],
        number_issues=report_service.number_issues(report),
        ai_available=report_ai.is_configured(),
        ai_model=report.ai_model,
        ai_generated_at=report.ai_generated_at,
        approved_by=f"{approver.first_name} {approver.last_name}" if approver else None,
        approved_at=report.approved_at,
        pdf_ready=report.status in PDF_READY,
        created_at=report.created_at,
    )


def _pdf_response(content: bytes, report: Report, *, suffix: str = "") -> Response:
    safe = "".join(ch if ch.isalnum() else "_" for ch in report.title)[:50] or "hisobot"
    filename = f"{safe}_v{report.version}{suffix}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("", response_model=Page[ReportListItem], summary="Reports")
async def list_reports(
    _: Viewer,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ReportListItem]:
    rows, total = await report_service.list_reports(db, limit=limit, offset=offset)
    return Page[ReportListItem](
        items=[
            ReportListItem(
                id=report.id,
                kind=report.kind,
                event_id=report.event_id,
                event_title=event_title,
                version=report.version,
                status=report.status,
                title=report.title,
                created_at=report.created_at,
                approved_at=report.approved_at,
                pdf_ready=report.status in PDF_READY,
            )
            for report, event_title in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ReportDetailOut, status_code=status.HTTP_201_CREATED, summary="Start a report")
async def create_report(payload: ReportCreateIn, current: Creator, db: DbSession) -> ReportDetailOut:
    report = await report_service.create_report(
        db,
        actor_id=current.user.id,
        kind=payload.kind,
        event_id=payload.event_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        title=payload.title.strip() if payload.title else None,
    )
    return await _detail(db, report)


@router.get("/{report_id}", response_model=ReportDetailOut, summary="Report with facts and photos")
async def get_report(report_id: uuid.UUID, _: Viewer, db: DbSession) -> ReportDetailOut:
    return await _detail(db, await report_service.get_report(db, report_id))


@router.patch("/{report_id}", response_model=ReportDetailOut, summary="Edit admin text or the draft")
async def update_report(
    report_id: uuid.UUID, payload: ReportUpdateIn, current: Creator, db: DbSession
) -> ReportDetailOut:
    report = await report_service.update_report(
        db, actor_id=current.user.id, report_id=report_id, changes=payload.model_dump(exclude_unset=True)
    )
    return await _detail(db, report)


@router.post("/{report_id}/refresh-facts", response_model=ReportDetailOut, summary="Reload facts from the database")
async def refresh_facts(report_id: uuid.UUID, current: Creator, db: DbSession) -> ReportDetailOut:
    return await _detail(db, await report_service.refresh_facts(db, actor_id=current.user.id, report_id=report_id))


@router.post("/{report_id}/generate", response_model=ReportDetailOut, summary="Draft the text (AI or template)")
async def generate(report_id: uuid.UUID, payload: GenerateIn, current: Creator, db: DbSession) -> ReportDetailOut:
    report = await report_service.draft(db, actor_id=current.user.id, report_id=report_id, use_ai=payload.use_ai)
    return await _detail(db, report)


@router.post("/{report_id}/approve", response_model=ReportDetailOut, summary="Approve and create the official PDF")
async def approve(report_id: uuid.UUID, current: Approver, db: DbSession) -> ReportDetailOut:
    return await _detail(db, await report_service.approve(db, actor_id=current.user.id, report_id=report_id))


@router.post("/{report_id}/archive", response_model=ReportDetailOut, summary="Move an approved report to the archive")
async def archive(report_id: uuid.UUID, current: Approver, db: DbSession) -> ReportDetailOut:
    return await _detail(db, await report_service.archive(db, actor_id=current.user.id, report_id=report_id))


@router.post(
    "/{report_id}/new-version",
    response_model=ReportDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Start a corrected version",
)
async def new_version(report_id: uuid.UUID, current: Creator, db: DbSession) -> ReportDetailOut:
    return await _detail(db, await report_service.new_version(db, actor_id=current.user.id, report_id=report_id))


@router.get("/{report_id}/pdf", summary="Official PDF (approved reports)")
async def download_pdf(report_id: uuid.UUID, _: Viewer, db: DbSession) -> Response:
    report = await report_service.get_report(db, report_id)
    return _pdf_response(await report_service.pdf_bytes(db, report), report)


@router.get("/{report_id}/preview.pdf", summary="Draft preview with a QORALAMA mark (not stored)")
async def preview_pdf(report_id: uuid.UUID, _: Viewer, db: DbSession) -> Response:
    report = await report_service.get_report(db, report_id)
    content = await report_pdf.render_report_pdf(db, report, draft=report.status not in report_service.FINAL_STATUSES)
    return _pdf_response(content, report, suffix="_qoralama")


@router.post(
    "/{report_id}/photos",
    response_model=ReportPhotoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an event photo (JPG/PNG/WEBP, up to 8 MB)",
)
async def upload_photo(
    report_id: uuid.UUID,
    current: Creator,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    caption: Annotated[str | None, Form(max_length=255)] = None,
) -> ReportPhotoOut:
    data = await file.read(report_service.MAX_PHOTO_BYTES + 1)
    photo = await report_service.add_photo(
        db,
        actor_id=current.user.id,
        report_id=report_id,
        data=data,
        content_type=file.content_type or "",
        caption=caption,
    )
    return ReportPhotoOut(id=photo.id, caption=photo.caption, size_bytes=photo.size_bytes)


@router.get("/{report_id}/photos/{photo_id}", summary="Photo file")
async def get_photo(report_id: uuid.UUID, photo_id: uuid.UUID, _: Viewer, db: DbSession) -> Response:
    photo = await report_service.get_photo(db, report_id, photo_id)
    return Response(content=await get_storage().get(photo.object_key), media_type=photo.content_type)


@router.delete("/{report_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a photo")
async def delete_photo(report_id: uuid.UUID, photo_id: uuid.UUID, current: Creator, db: DbSession) -> Response:
    await report_service.delete_photo(db, actor_id=current.user.id, report_id=report_id, photo_id=photo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
