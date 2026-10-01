"""Official report PDF: an HTML/CSS template rendered by WeasyPrint (A4, serif type, tables)."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import Report, User
from app.services.storage import get_storage
from app.utils.timezone import format_datetime

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


@lru_cache
def _environment() -> Environment:
    return Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


def body_blocks(text: str | None) -> list[dict[str, str]]:
    """Split the approved text into headings ("## ...") and paragraphs (blank-line separated)."""
    blocks: list[dict[str, str]] = []
    for chunk in (text or "").replace("\r\n", "\n").split("\n\n"):
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        paragraph: list[str] = []
        for line in lines:
            if line.startswith("#"):
                if paragraph:
                    blocks.append({"kind": "paragraph", "text": " ".join(paragraph)})
                    paragraph = []
                blocks.append({"kind": "heading", "text": line.lstrip("#").strip()})
            else:
                paragraph.append(line)
        if paragraph:
            blocks.append({"kind": "paragraph", "text": " ".join(paragraph)})
    return blocks


async def _photos(session: AsyncSession, report: Report) -> list[dict[str, Any]]:
    from app.services.reports import list_photos

    storage = get_storage()
    result = []
    for photo in await list_photos(session, report.id):
        try:
            data = await storage.get(photo.object_key)
        except AppError:
            continue  # a lost file (e.g. rebuilt free server) must not block the PDF
        encoded = base64.b64encode(data).decode("ascii")
        result.append({"src": f"data:{photo.content_type};base64,{encoded}", "caption": photo.caption})
    return result


async def render_report_pdf(session: AsyncSession, report: Report, *, draft: bool) -> bytes:
    from weasyprint import HTML  # heavy import, only when a PDF is needed

    approver = await session.get(User, report.approved_by) if report.approved_by else None
    facts = report.facts_snapshot or {}
    prepared = facts.get("prepared_at")
    html = (
        _environment()
        .get_template("report.html")
        .render(
            report=report,
            facts=facts,
            body=body_blocks(report.body_text),
            photos=await _photos(session, report),
            draft=draft,
            approved_by=f"{approver.first_name} {approver.last_name}" if approver else None,
            approved_at=format_datetime(report.approved_at) if report.approved_at else None,
            prepared_at=format_datetime(datetime.fromisoformat(prepared)) if prepared else "—",
            footer_left=f"Hisobot {str(report.id)[:8]} · {report.version}-versiya",
        )
    )
    return await asyncio.to_thread(lambda: HTML(string=html, base_url=str(TEMPLATES)).write_pdf())
