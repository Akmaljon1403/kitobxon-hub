"""One document, three files: Excel (XLSX), Word (DOCX) and PDF.

The builders in ``app.services.documents`` describe a document once (title, lines under it, tables,
an appendix with QR codes); this module turns it into the file the admin asked for.
"""

from __future__ import annotations

import asyncio
import base64
import io
from dataclasses import dataclass, field
from typing import Any

import segno

from app.utils.spreadsheet import safe_cell

MIME = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@dataclass
class Table:
    title: str | None
    columns: list[str]
    rows: list[list[Any]]
    totals: list[Any] | None = None
    widths: list[float] | None = None  # relative widths for Word and PDF


@dataclass
class QrEntry:
    """One person in the appendix: a QR code anyone can scan to check them."""

    title: str
    details: str
    url: str


@dataclass
class Document:
    title: str
    filename: str  # without the extension
    lines: list[str] = field(default_factory=list)  # under the title: organisation, period, filters
    tables: list[Table] = field(default_factory=list)
    appendix_title: str | None = None
    appendix: list[QrEntry] = field(default_factory=list)
    landscape: bool = False
    signature: str | None = None  # «Klub rahbari: ________»


# ---------------------------------------------------------------------------- Excel


def to_xlsx(document: Document) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    workbook.remove(workbook.active)
    header_fill = PatternFill("solid", fgColor="1F5132")
    thin = Side(style="thin", color="C9D3CC")
    tables = list(document.tables)
    if document.appendix:
        tables.append(
            Table(
                document.appendix_title or "Ilova",
                ["№", "F.I.Sh.", "Ma'lumot", "Tekshirish havolasi"],
                [[index, entry.title, entry.details, entry.url] for index, entry in enumerate(document.appendix, 1)],
            )
        )
    used: set[str] = set()
    for number, table in enumerate(tables, start=1):
        name = (table.title or document.title)[:28].replace("/", "-").replace(":", " ") or f"Varaq {number}"
        while name in used:
            name = f"{name[:25]} {number}"
        used.add(name)
        sheet = workbook.create_sheet(name)
        row_index = 1
        sheet.cell(row=1, column=1, value=safe_cell(document.title)).font = Font(bold=True, size=14)
        for line in document.lines:
            row_index += 1
            sheet.cell(row=row_index, column=1, value=safe_cell(line)).font = Font(color="555555")
        if table.title:
            row_index += 1
            sheet.cell(row=row_index, column=1, value=safe_cell(table.title)).font = Font(bold=True, size=12)
        row_index += 2
        header_row = row_index
        for column, title in enumerate(table.columns, start=1):
            cell = sheet.cell(row=row_index, column=column, value=title)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        for values in table.rows:
            row_index += 1
            for column, value in enumerate(values, start=1):
                cell = sheet.cell(row=row_index, column=column, value=safe_cell(value))
                cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        if table.totals:
            row_index += 1
            for column, value in enumerate(table.totals, start=1):
                cell = sheet.cell(row=row_index, column=column, value=safe_cell(value))
                cell.font = Font(bold=True)
        for column, title in enumerate(table.columns, start=1):
            longest = max(
                [len(str(title))] + [len(str(row[column - 1])) for row in table.rows if column - 1 < len(row)]
            )
            sheet.column_dimensions[get_column_letter(column)].width = min(max(longest + 2, 6), 48)
        if table.rows:
            sheet.auto_filter.ref = (
                f"A{header_row}:{get_column_letter(len(table.columns))}{header_row + len(table.rows)}"
            )
        sheet.freeze_panes = sheet.cell(row=header_row + 1, column=1)
    if not workbook.sheetnames:
        workbook.create_sheet("Hujjat").cell(row=1, column=1, value=document.title)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------- Word


def _qr_png(url: str) -> bytes:
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=6, border=1, dark="#14402c")
    return buffer.getvalue()


def to_docx(document: Document) -> bytes:
    from docx import Document as WordDocument
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    word = WordDocument()
    section = word.sections[0]
    if document.landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(1.6))
    style = word.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)

    heading = word.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = heading.add_run(document.title)
    run.bold = True
    run.font.size = Pt(15)
    for line in document.lines:
        paragraph = word.add_paragraph(line)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    for table in document.tables:
        if table.title:
            title = word.add_paragraph()
            title_run = title.add_run(table.title)
            title_run.bold = True
            title_run.font.size = Pt(12)
        grid = word.add_table(rows=1, cols=len(table.columns))
        grid.style = "Table Grid"
        for index, name in enumerate(table.columns):
            cell = grid.rows[0].cells[index]
            cell.text = ""
            header_run = cell.paragraphs[0].add_run(str(name))
            header_run.bold = True
            header_run.font.size = Pt(9.5)
        for values in [*table.rows, *([table.totals] if table.totals else [])]:
            cells = grid.add_row().cells
            for index, value in enumerate(values[: len(table.columns)]):
                cells[index].text = "" if value is None else str(value)
                for paragraph in cells[index].paragraphs:
                    for cell_run in paragraph.runs:
                        cell_run.font.size = Pt(9.5)
                        cell_run.bold = values is table.totals
        word.add_paragraph()

    if document.appendix:
        word.add_page_break()
        title = word.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        appendix_run = title.add_run(document.appendix_title or "Ilova")
        appendix_run.bold = True
        appendix_run.font.size = Pt(13)
        columns = 3
        grid = word.add_table(rows=0, cols=columns)
        grid.style = "Table Grid"
        cells: list[Any] = []
        for number, entry in enumerate(document.appendix, start=1):
            if (number - 1) % columns == 0:
                cells = grid.add_row().cells
            cell = cells[(number - 1) % columns]
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.add_run().add_picture(io.BytesIO(_qr_png(entry.url)), width=Cm(2.6))
            name = cell.add_paragraph()
            name.alignment = WD_ALIGN_PARAGRAPH.CENTER
            name_run = name.add_run(f"{number}. {entry.title}")
            name_run.bold = True
            name_run.font.size = Pt(9)
            details = cell.add_paragraph(entry.details)
            details.alignment = WD_ALIGN_PARAGRAPH.CENTER
            details.runs[0].font.size = Pt(8)
    if document.signature:
        word.add_paragraph()
        word.add_paragraph(document.signature)
    output = io.BytesIO()
    word.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------- PDF


def _pdf_html(document: Document) -> str:
    from app.services.report_pdf import _environment

    appendix = [
        {
            "title": entry.title,
            "details": entry.details,
            "qr": "data:image/png;base64," + base64.b64encode(_qr_png(entry.url)).decode("ascii"),
        }
        for entry in document.appendix
    ]
    return _environment().get_template("document.html").render(doc=document, appendix=appendix)


async def to_pdf(document: Document) -> bytes:
    from weasyprint import HTML

    from app.services.report_pdf import TEMPLATES

    html = _pdf_html(document)
    return await asyncio.to_thread(lambda: HTML(string=html, base_url=str(TEMPLATES)).write_pdf())


async def render(document: Document, fmt: str) -> bytes:
    if fmt == "xlsx":
        return await asyncio.to_thread(to_xlsx, document)
    if fmt == "docx":
        return await asyncio.to_thread(to_docx, document)
    return await to_pdf(document)
