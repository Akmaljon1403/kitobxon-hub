"""«📄 Hujjatlar»: every document in Excel, Word or PDF — downloaded, or sent to the admin in the bot
(inside Telegram a file cannot be saved from the panel, so the bot brings it)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from aiogram.types import BufferedInputFile
from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentAdminDep, DbSession
from app.api.v1.endpoints.my_documents import file_response
from app.core.errors import ForbiddenError, NotFoundError
from app.services import delivery, documents
from app.services.document_render import MIME

router = APIRouter(prefix="/admin/documents", tags=["admin: documents"])
Format = Literal["xlsx", "pdf", "docx"]


class TemplateOut(BaseModel):
    code: str
    title: str
    description: str
    formats: list[str]
    params: list[str]


class DocumentParams(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    faculty_id: uuid.UUID | None = None
    course: int | None = Field(default=None, ge=1, le=8)
    group_name: str | None = Field(default=None, max_length=32)
    event_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    report_id: uuid.UUID | None = None


class SendIn(DocumentParams):
    format: Format


def _allowed(current: CurrentAdminDep, code: str) -> documents.Template:
    template = documents.BY_CODE.get(code)
    if template is None:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Bunday hujjat yo'q.")
    if template.permission.value not in current.permissions:
        raise ForbiddenError("PERMISSION_DENIED", "Bu hujjat uchun ruxsatingiz yo'q.")
    return template


def _params(payload: DocumentParams) -> documents.Params:
    return documents.Params(**payload.model_dump(exclude={"format"}))


@router.get("", response_model=list[TemplateOut], summary="The documents this admin may prepare")
async def templates(current: CurrentAdminDep) -> list[TemplateOut]:
    return [
        TemplateOut(
            code=template.code,
            title=template.title,
            description=template.description,
            formats=list(template.formats),
            params=list(template.params),
        )
        for template in documents.TEMPLATES
        if template.permission.value in current.permissions
    ]


@router.get("/{code}/file", summary="Download a document", response_class=Response)
async def download(
    code: str,
    current: CurrentAdminDep,
    db: DbSession,
    format: Annotated[Format, Query()] = "xlsx",
    date_from: date | None = None,
    date_to: date | None = None,
    faculty_id: uuid.UUID | None = None,
    course: Annotated[int | None, Query(ge=1, le=8)] = None,
    group_name: Annotated[str | None, Query(max_length=32)] = None,
    event_id: uuid.UUID | None = None,
    test_id: uuid.UUID | None = None,
    report_id: uuid.UUID | None = None,
) -> Response:
    _allowed(current, code)
    params = documents.Params(
        date_from=date_from,
        date_to=date_to,
        faculty_id=faculty_id,
        course=course,
        group_name=group_name,
        event_id=event_id,
        test_id=test_id,
        report_id=report_id,
    )
    name, data = await documents.produce(db, code, format, params)
    return file_response(data, MIME[format], name, attachment=True)


@router.post("/{code}/send", status_code=status.HTTP_204_NO_CONTENT, summary="The bot sends me the document")
async def send(code: str, payload: SendIn, current: CurrentAdminDep, db: DbSession) -> Response:
    template = _allowed(current, code)
    name, data = await documents.produce(db, code, payload.format, _params(payload))
    bot = delivery.runtime_bot()
    await delivery.explain_failures(
        bot.send_document(
            current.user.telegram_id,
            BufferedInputFile(data, filename=name),
            caption=f"📄 <b>{template.title}</b>",
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
