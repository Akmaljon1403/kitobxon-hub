"""Questions from a file: TXT, Word (DOCX) or PDF — with pictures.

The admin prepares the questions as usual, for example::

    1. «O'tkan kunlar» romani muallifi kim?
    A) Cho'lpon
    *B) Abdulla Qodiriy
    C) Oybek
    Izoh: Roman 1922–1925-yillarda yozilgan.

* a question starts with a number («1.» or «1)»), «?» or «Savol:»;
* answers are «A)», «B.», … or «+ …» / «- …» lines;
* the correct answer is marked with «*», «+» or «#» (before or after it), or with a line
  «Javob: B» (several: «Javob: A, C»), or — in Word — written in bold or highlighted;
* «Izoh: …» is the explanation shown after the test; «(2 ball)» in a question gives it 2 points;
* a picture placed in Word (or a PDF) under a question belongs to that question.

Nothing is saved here: the questions come back to the editor, the admin checks them and saves.
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import BadRequestError
from app.models.enums import QuestionType

logger = logging.getLogger(__name__)

MAX_BYTES = 15 * 1024 * 1024
MAX_QUESTIONS = 200
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIN_IMAGE_SIDE = 40  # smaller pictures are decorations (bullets, lines)

_QUESTION = re.compile(r"^\s*(?:(?:savol|question|вопрос)\s*)?(\d{1,3})\s*[.)]\s*(?P<text>\S.*)$", re.IGNORECASE)
_QUESTION_MARK = re.compile(r"^\s*(?:\?|savol\s*:)\s*(?P<text>\S.*)$", re.IGNORECASE)
_LETTERS = "ABCDEFGHАБВГДЕЁЖ"
_OPTION = re.compile(
    r"^\s*(?P<before>[*+#✓✔]\s*)?(?P<letter>[A-Ha-hА-Жа-ж])\s*[).]\s*(?P<text>.*?)\s*(?P<after>[*+#✓✔])?\s*$"
)
_SIGNED = re.compile(r"^\s*(?P<sign>[+\-–])\s+(?P<text>\S.*)$")
_ANSWER = re.compile(
    r"^\s*(?:to['ʻ’`]?g['ʻ’`]?ri\s+)?(?:javob(?:i)?|answer|ответ|kalit)\s*[:\-–]\s*(?P<letters>[A-Ha-hА-Жа-ж](?:\s*[,;]?\s*[A-Ha-hА-Жа-ж])*)\s*\.?$",
    re.IGNORECASE,
)
_EXPLANATION = re.compile(r"^\s*(?:izoh|tushuntirish|explanation|пояснение)\s*[:\-–]\s*(?P<text>.*)$", re.IGNORECASE)
_POINTS = re.compile(r"\(\s*(\d{1,2})\s*(?:ball|bal|балл|point)s?\s*\)", re.IGNORECASE)


@dataclass
class Piece:
    """One line of text (``marked``: bold/highlighted in Word) or one picture, in reading order."""

    text: str = ""
    image: bytes | None = None
    marked: bool = False


@dataclass
class Draft:
    text: str
    options: list[dict[str, Any]] = field(default_factory=list)
    marked: list[bool] = field(default_factory=list)
    answer_letters: str = ""
    explanation: str | None = None
    images: list[bytes] = field(default_factory=list)
    points: int = 1


# ---------------------------------------------------------------------------- reading the file


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if encoding != "utf-16" or text.count("\x00") == 0:
            return text
    return data.decode("utf-8", errors="replace")


def read_txt(data: bytes) -> list[Piece]:
    return [Piece(text=line) for line in _decode(data).splitlines()]


def read_docx(data: bytes) -> list[Piece]:
    from docx import Document
    from docx.oxml.ns import qn

    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise BadRequestError("IMPORT_UNREADABLE", "Word faylini o'qib bo'lmadi. .docx formatida saqlang.") from exc
    pieces: list[Piece] = []
    related = document.part.related_parts

    def paragraph(element: Any) -> None:
        texts: list[str] = []
        runs_marked: list[bool] = []
        for run in element.iter(qn("w:r")):
            parts: list[str] = []
            for node in run.iter():
                if node.tag == qn("w:t"):
                    parts.append(node.text or "")
                elif node.tag == qn("w:tab"):
                    parts.append(" ")
                elif node.tag in (qn("w:br"), qn("w:cr")):
                    parts.append("\n")
                elif node.tag == qn("a:blip"):
                    rel = node.get(qn("r:embed"))
                    part = related.get(rel) if rel else None
                    if part is not None:
                        pieces.append(Piece(image=part.blob))
            text = "".join(parts)
            if text.strip():
                props = run.find(qn("w:rPr"))
                bold = props is not None and props.find(qn("w:b")) is not None and _on(props.find(qn("w:b")))
                highlight = props is not None and (
                    props.find(qn("w:highlight")) is not None or props.find(qn("w:shd")) is not None
                )
                runs_marked.append(bool(bold or highlight))
            texts.append(text)
        marked = bool(runs_marked) and all(runs_marked)
        for chunk in "".join(texts).split("\n"):  # Shift+Enter makes several lines in one paragraph
            pieces.append(Piece(text=chunk, marked=marked))

    for element in document.element.body.iterchildren():
        if element.tag == qn("w:p"):
            paragraph(element)
        elif element.tag == qn("w:tbl"):
            for cell_paragraph in element.iter(qn("w:p")):
                paragraph(cell_paragraph)
    return pieces


def _on(node: Any) -> bool:
    from docx.oxml.ns import qn

    value = node.get(qn("w:val")) if node is not None else None
    return value not in ("0", "false", "off")


def read_pdf(data: bytes) -> list[Piece]:
    """Text lines and pictures of every page, top to bottom."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    try:
        document = pdfium.PdfDocument(data)
    except Exception as exc:
        raise BadRequestError("IMPORT_UNREADABLE", "PDF faylini o'qib bo'lmadi.") from exc
    pieces: list[Piece] = []
    try:
        for page in document:
            textpage = page.get_textpage()
            lines: list[tuple[float, float, str]] = []  # (top, left, text)
            for index in range(textpage.count_rects()):
                left, bottom, right, top = textpage.get_rect(index)
                text = textpage.get_text_bounded(left, bottom, right, top).strip("\r\n")
                if text.strip():
                    lines.append((top, left, text))
            merged = _merge_lines(lines)
            items: list[tuple[float, Piece]] = [(top, Piece(text=text)) for top, text in merged]
            for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE], max_depth=2):
                try:
                    left, bottom, right, top = obj.get_bounds()
                    picture = obj.get_bitmap(render=True).to_pil()
                except Exception:  # an unusual image encoding: skip the picture, keep the text
                    logger.info("A picture in the PDF could not be read")
                    continue
                if min(picture.size) < MIN_IMAGE_SIDE:
                    continue
                buffer = io.BytesIO()
                picture.convert("RGB").save(buffer, format="PNG")
                items.append((top, Piece(image=buffer.getvalue())))
            items.sort(key=lambda item: -item[0])
            pieces.extend(piece for _, piece in items)
            if not merged:  # no text rectangles (unusual PDF): plain text of the page
                pieces.extend(Piece(text=line) for line in textpage.get_text_range().splitlines())
    finally:
        document.close()
    return pieces


def _merge_lines(rects: list[tuple[float, float, str]]) -> list[tuple[float, str]]:
    """Text rectangles on the same line (close tops) joined left to right."""
    rects.sort(key=lambda item: (-item[0], item[1]))
    lines: list[tuple[float, list[tuple[float, str]]]] = []
    for top, left, text in rects:
        if lines and abs(lines[-1][0] - top) < 3:
            lines[-1][1].append((left, text))
        else:
            lines.append((top, [(left, text)]))
    return [(top, " ".join(text for _, text in sorted(parts))) for top, parts in lines]


def read(filename: str, data: bytes) -> list[Piece]:
    if not data:
        raise BadRequestError("IMPORT_EMPTY", "Fayl bo'sh.")
    if len(data) > MAX_BYTES:
        raise BadRequestError("IMPORT_TOO_LARGE", "Fayl 15 MB dan oshmasin.")
    name = filename.lower()
    if name.endswith(".docx") or data[:2] == b"PK":
        return read_docx(data)
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        return read_pdf(data)
    if name.endswith((".txt", ".text", ".csv")) or not name.rpartition(".")[1]:
        return read_txt(data)
    raise BadRequestError("IMPORT_FORMAT", "TXT, Word (.docx) yoki PDF fayl yuboring.")


# ---------------------------------------------------------------------------- understanding the questions


def _letter_index(letter: str) -> int:
    upper = letter.upper()
    latin = "ABCDEFGH"
    if upper in latin:
        return latin.index(upper)
    cyrillic = "АБВГДЕЖ"
    return cyrillic.index(upper) if upper in cyrillic else -1


def parse(pieces: list[Piece]) -> list[Draft]:
    drafts: list[Draft] = []
    current: Draft | None = None
    last_option: dict[str, Any] | None = None
    pending_images: list[bytes] = []  # pictures before the first question

    def start(text: str) -> Draft:
        nonlocal last_option
        draft = Draft(text=text.strip())
        drafts.append(draft)
        last_option = None
        return draft

    for piece in pieces:
        if piece.image is not None:
            if current is None:
                pending_images.append(piece.image)
            else:
                current.images.append(piece.image)
            continue
        line = piece.text.replace(" ", " ").rstrip()
        if not line.strip():
            continue
        if match := _ANSWER.match(line):
            if current is not None:
                current.answer_letters += re.sub(r"[^A-Ha-hА-Жа-ж]", "", match["letters"])
            continue
        if match := _EXPLANATION.match(line):
            if current is not None:
                current.explanation = match["text"].strip() or None
            continue
        option = _OPTION.match(line)
        if option and current is not None and option["text"].strip():
            correct = bool(option["before"] or option["after"])
            last_option = {"text": option["text"].strip(), "is_correct": correct, "letter": option["letter"]}
            current.options.append(last_option)
            current.marked.append(piece.marked)
            continue
        signed = _SIGNED.match(line)
        if signed and current is not None:
            last_option = {"text": signed["text"].strip(), "is_correct": signed["sign"] == "+", "letter": None}
            current.options.append(last_option)
            current.marked.append(piece.marked)
            continue
        question = _QUESTION.match(line) or _QUESTION_MARK.match(line)
        if question:
            current = start(question["text"])
            if pending_images:
                current.images.extend(pending_images)
                pending_images = []
            continue
        if current is None:
            continue  # a title or instructions before the first question
        if last_option is not None:
            last_option["text"] = f"{last_option['text']} {line.strip()}"
        else:
            current.text = f"{current.text}\n{line.strip()}"
    return drafts


def to_questions(drafts: list[Draft]) -> tuple[list[dict[str, Any]], list[str]]:
    """Editor-ready questions and warnings about what the admin should check."""
    questions: list[dict[str, Any]] = []
    warnings: list[str] = []
    for number, draft in enumerate(drafts[:MAX_QUESTIONS], start=1):
        text = draft.text
        if points := _POINTS.search(text):
            draft.points = max(1, min(int(points.group(1)), 100))
            text = _POINTS.sub("", text).strip()
        options = draft.options[:10]
        if draft.answer_letters:
            wanted = {_letter_index(letter) for letter in draft.answer_letters}
            for index, option in enumerate(options):
                letter = option.get("letter")
                position = _letter_index(letter) if letter else index
                option["is_correct"] = position in wanted
        if not any(option["is_correct"] for option in options) and any(draft.marked[: len(options)]):
            marked = draft.marked[: len(options)]
            if 0 < sum(marked) < len(options):  # bold/highlighted answers in Word
                for option, is_marked in zip(options, marked, strict=False):
                    option["is_correct"] = is_marked
        correct = sum(1 for option in options if option["is_correct"])
        if len(options) < 2:
            warnings.append(f"{number}-savol: variantlar topilmadi")
        elif correct == 0:
            warnings.append(f"{number}-savol: to'g'ri javob belgilanmagan")
        if len(draft.options) > 10:
            warnings.append(f"{number}-savol: 10 tadan ortiq variant — birinchi 10 tasi olindi")
        questions.append(
            {
                "type": QuestionType.MULTIPLE_CHOICE if correct > 1 else QuestionType.SINGLE_CHOICE,
                "text": text[:2000],
                "points": draft.points,
                "explanation": (draft.explanation or None) and draft.explanation[:2000],
                "options": [{"text": option["text"][:500], "is_correct": option["is_correct"]} for option in options],
                "images": draft.images[:1],
            }
        )
        if len(draft.images) > 1:
            warnings.append(f"{number}-savol: bir nechta rasm bor — birinchisi olindi")
    if len(drafts) > MAX_QUESTIONS:
        warnings.append(f"Faylda {len(drafts)} ta savol bor — birinchi {MAX_QUESTIONS} tasi olindi")
    return questions, warnings


def prepare_image(data: bytes) -> bytes:
    """A question picture: checked, turned upright, at most 1600 px, without metadata (JPEG)."""
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise BadRequestError("IMAGE_TOO_LARGE", "Rasm 8 MB dan oshmasin.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 40_000_000:
            raise BadRequestError("IMAGE_TOO_LARGE", "Rasm o'lchami juda katta.")
        image.verify()
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise BadRequestError("IMAGE_INVALID", "Rasm faylini tanlang (JPG yoki PNG).") from exc
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")
    image.thumbnail((1600, 1600))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88)
    return output.getvalue()


def image_key(test_id: uuid.UUID) -> str:
    return f"tests/{test_id}/q-{uuid.uuid4().hex}.jpg"


async def import_file(test_id: uuid.UUID, filename: str, data: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    """Read a file into editor-ready questions; their pictures are stored and referenced by key."""
    import asyncio

    from app.services.storage import get_storage

    pieces = await asyncio.to_thread(read, filename, data)
    drafts = parse(pieces)
    if not drafts:
        raise BadRequestError(
            "IMPORT_NO_QUESTIONS",
            "Faylda savol topilmadi. Har bir savol raqam bilan boshlansin («1. …»), variantlar «A) …» ko'rinishida.",
        )
    questions, warnings = to_questions(drafts)
    storage = get_storage()
    for number, question in enumerate(questions, start=1):
        images = question.pop("images")
        question["image_key"] = None
        if not images:
            continue
        try:
            prepared = await asyncio.to_thread(prepare_image, images[0])
        except BadRequestError:
            warnings.append(f"{number}-savol: rasmni o'qib bo'lmadi")
            continue
        key = image_key(test_id)
        await storage.put(key, prepared, "image/jpeg")
        question["image_key"] = key
    return questions, warnings
