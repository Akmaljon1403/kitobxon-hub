"""Pictures members share: a saved quote as a card («💬 Iqtiboslar sandig'i») and «🪪 Kitobxonlik
kartam» (the books, pages, streak and points of a reader on one card).

Drawn with Pillow in the club's colours (navy and gold) and fonts (Lora for quotes, Montserrat for the
rest, bundled in ``app/brand/fonts``), 1080 × 1350 — the shape Telegram and Instagram show best.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, Faculty, SavedQuote, ShelfItem, User, UserAchievement
from app.models.enums import ShelfStatus
from app.utils.timezone import local_tz

WIDTH, HEIGHT = 1080, 1350
FONTS = Path(__file__).resolve().parent.parent / "brand" / "fonts"
NAVY950 = (5, 14, 29)
NAVY = (11, 31, 59)
NAVY700 = (19, 43, 79)
NAVY600 = (28, 58, 102)
GOLD = (212, 175, 55)
GOLD300 = (239, 216, 135)
CREAM = (248, 246, 242)
MUTED = (178, 190, 210)

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


@cache
def _font(name: str, size: int) -> Font:
    path = FONTS / name
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    for fallback in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if Path(fallback).is_file():
            return ImageFont.truetype(fallback, size)
    return ImageFont.load_default(size)


def quote_font(size: int) -> Font:
    return _font("lora-latin-500-italic.woff", size)


def sans(size: int, weight: int = 600) -> Font:
    return _font(f"montserrat-latin-{weight}-normal.woff", size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: Font) -> float:
    return draw.textlength(text, font=font)


def wrap(draw: ImageDraw.ImageDraw, text: str, font: Font, width: int) -> list[str]:
    """Words into lines no wider than ``width`` (a too long word is cut)."""
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if _text_width(draw, candidate, font) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
            while _text_width(draw, word, font) > width and len(word) > 1:
                cut = len(word)
                while cut > 1 and _text_width(draw, word[:cut], font) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            line = word
        lines.append(line)
    return [line for line in lines if line is not None]


def _background() -> Image.Image:
    """Navy from top to bottom with a soft light near the top and a double gold frame."""
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(
            round(NAVY600[i] * (1 - t) ** 2 + NAVY[i] * 2 * t * (1 - t) + NAVY950[i] * t**2) for i in range(3)
        )
        draw.line([(0, y), (WIDTH, y)], fill=color)
    glow = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(glow).ellipse((WIDTH * 0.1, -HEIGHT * 0.25, WIDTH * 0.9, HEIGHT * 0.35), fill=40)
    from PIL import ImageFilter

    glow = glow.filter(ImageFilter.GaussianBlur(120))
    image.paste(Image.new("RGB", (WIDTH, HEIGHT), GOLD300), (0, 0), glow)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((36, 36, WIDTH - 36, HEIGHT - 36), radius=36, outline=GOLD, width=4)
    draw.rounded_rectangle((52, 52, WIDTH - 52, HEIGHT - 52), radius=28, outline=(*GOLD,), width=1)
    _sparkles(draw)
    return image


def _star(draw: ImageDraw.ImageDraw, x: float, y: float, r: float, color: tuple[int, int, int]) -> None:
    """A four-pointed sparkle (drawn, so no font needs the glyph)."""
    inner = r * 0.28
    points = [
        (x, y - r),
        (x + inner, y - inner),
        (x + r, y),
        (x + inner, y + inner),
        (x, y + r),
        (x - inner, y + inner),
        (x - r, y),
        (x - inner, y - inner),
    ]
    draw.polygon(points, fill=color)


def _sparkles(draw: ImageDraw.ImageDraw) -> None:
    # Near the frame, away from the lines of text at the bottom.
    for x, y, r in ((120, 150, 9), (960, 210, 7), (990, 1110, 10), (92, 1262, 6), (990, 640, 5), (90, 720, 5)):
        _star(draw, x, y, r, GOLD300)


def _logo(image: Image.Image, center_x: int, top: int, height: int) -> None:
    from app.services.brand import BRAND

    for name in ("logo-mark-dark.png", "logo-badge.png", "logo-mark.png"):
        path = BRAND / name
        if path.is_file():
            with Image.open(path) as source:
                mark = source.convert("RGBA")
            mark.thumbnail((height * 3, height))
            image.paste(mark, (center_x - mark.width // 2, top), mark)
            return


def _centered(draw: ImageDraw.ImageDraw, y: float, text: str, font: Font, fill: tuple[int, ...]) -> None:
    draw.text(((WIDTH - _text_width(draw, text, font)) / 2, y), text, font=font, fill=fill)


def _spaced(text: str) -> str:
    return " ".join(text.upper())


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


# ---------------------------------------------------------------------------- quote and thought cards


@dataclass(frozen=True)
class Style:
    """One look of a card: how the background is drawn and the colours of the words on it."""

    code: str
    title: str
    text: tuple[int, int, int]
    accent: tuple[int, int, int]
    soft: tuple[int, int, int]  # the source line
    muted: tuple[int, int, int]  # «Yubordi: …»
    light: bool  # a light background (the dark logo is used)


STYLES: dict[str, Style] = {
    style.code: style
    for style in (
        Style("classic", "Klassik (to'q ko'k va oltin)", CREAM, GOLD, GOLD300, MUTED, False),
        Style("paper", "Qog'oz (kitob sahifasi)", (43, 33, 24), (122, 31, 43), (110, 72, 40), (125, 108, 88), True),
        Style("night", "Tungi osmon", (246, 243, 255), (201, 182, 255), (226, 214, 255), (170, 160, 205), False),
        Style("emerald", "Zumrad", (244, 240, 226), GOLD, GOLD300, (166, 196, 180), False),
        Style("sunrise", "Tong", (52, 22, 34), (102, 30, 66), (92, 40, 56), (120, 70, 80), True),
        Style("minimal", "Minimal (oq)", (24, 24, 27), (176, 138, 40), (90, 90, 96), (130, 130, 136), True),
    )
}
DEFAULT_STYLE = "classic"


def style_of(code: str | None) -> Style:
    return STYLES.get(code or DEFAULT_STYLE, STYLES[DEFAULT_STYLE])


def _gradient(colors: list[tuple[int, int, int]]) -> Image.Image:
    """A top-to-bottom blend through the given colours."""
    image = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    steps = len(colors) - 1
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1) * steps
        index = min(int(t), steps - 1)
        local = t - index
        a, b = colors[index], colors[index + 1]
        draw.line([(0, y), (WIDTH, y)], fill=tuple(round(a[i] + (b[i] - a[i]) * local) for i in range(3)))
    return image


def _glow(image: Image.Image, color: tuple[int, int, int], box: tuple[float, ...], strength: int) -> None:
    from PIL import ImageFilter

    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(mask).ellipse(box, fill=strength)
    image.paste(Image.new("RGB", (WIDTH, HEIGHT), color), (0, 0), mask.filter(ImageFilter.GaussianBlur(120)))


def _style_background(style: Style) -> Image.Image:
    import random

    if style.code == "paper":
        image = _gradient([(250, 244, 230), (244, 235, 214), (236, 224, 198)])
        draw = ImageDraw.Draw(image)
        for y in range(470, 1030, 62):  # the ruled lines of a notebook page
            draw.line([(150, y), (WIDTH - 150, y)], fill=(226, 212, 184), width=2)
        draw.rectangle((40, 40, WIDTH - 40, HEIGHT - 40), outline=style.accent, width=3)
        draw.rectangle((54, 54, WIDTH - 54, HEIGHT - 54), outline=(196, 160, 120), width=1)
        return image
    if style.code == "night":
        image = _gradient([(36, 24, 84), (56, 30, 92), (14, 11, 38)])
        _glow(image, (140, 110, 230), (WIDTH * 0.15, -HEIGHT * 0.2, WIDTH * 0.85, HEIGHT * 0.3), 60)
        draw = ImageDraw.Draw(image)
        rng = random.Random(7)  # noqa: S311 — decoration: the same sky every time
        for _ in range(140):
            x, y, r = rng.randint(50, WIDTH - 50), rng.randint(50, HEIGHT - 50), rng.choice((1, 1, 1, 2, 2, 3))
            shade = rng.randint(150, 255)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(shade, shade, 255))
        for x, y, r in ((150, 170, 12), (930, 260, 9), (900, 1140, 11), (170, 1170, 8)):
            _star(draw, x, y, r, style.accent)
        draw.rounded_rectangle((36, 36, WIDTH - 36, HEIGHT - 36), radius=40, outline=style.accent, width=3)
        return image
    if style.code == "emerald":
        image = _gradient([(20, 84, 64), (12, 58, 45), (5, 30, 23)])
        _glow(image, GOLD300, (WIDTH * 0.1, -HEIGHT * 0.25, WIDTH * 0.9, HEIGHT * 0.35), 36)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((36, 36, WIDTH - 36, HEIGHT - 36), radius=36, outline=GOLD, width=4)
        draw.rounded_rectangle((52, 52, WIDTH - 52, HEIGHT - 52), radius=28, outline=GOLD, width=1)
        _sparkles(draw)
        return image
    if style.code == "sunrise":
        image = _gradient([(255, 226, 180), (250, 178, 140), (232, 128, 132)])
        _glow(image, (255, 248, 225), (WIDTH * 0.2, HEIGHT * 0.62, WIDTH * 0.8, HEIGHT * 1.15), 90)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((36, 36, WIDTH - 36, HEIGHT - 36), radius=44, outline=(255, 250, 240), width=4)
        return image
    if style.code == "minimal":
        image = Image.new("RGB", (WIDTH, HEIGHT), (252, 252, 250))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, WIDTH, 14), fill=style.accent)
        draw.rectangle((0, HEIGHT - 14, WIDTH, HEIGHT), fill=style.accent)
        return image
    return _background()


def _logo_for(image: Image.Image, style: Style, top: int, height: int) -> None:
    from app.services.brand import BRAND

    names = ("logo-mark-dark.png", "logo-badge.png") if style.light else ("logo-mark.png", "logo-badge.png")
    for name in names:
        path = BRAND / name
        if path.is_file():
            with Image.open(path) as source:
                mark = source.convert("RGBA")
            mark.thumbnail((height * 3, height))
            image.paste(mark, (WIDTH // 2 - mark.width // 2, top), mark)
            return


def styled_card(
    text: str,
    *,
    label: str,
    source: str | None,
    by: str | None,
    footer: str,
    style: str | None = None,
    by_prefix: str = "Yubordi",
) -> bytes:
    """A quote, a thought or an impression on a card in one of the ``STYLES``."""
    look = style_of(style)
    image = _style_background(look)
    draw = ImageDraw.Draw(image)
    _logo_for(image, look, 96, 110)
    _centered(draw, 222, _spaced(label), sans(22, 700), look.accent)
    mark_color = (226, 226, 222) if look.code == "minimal" else look.accent
    draw.text((112, 250), "\u201c", font=_font("lora-latin-600-italic.woff", 230), fill=mark_color)

    box_top, box_bottom, box_width = 420, 1010, WIDTH - 2 * 140
    size, lines = 66, []
    while size >= 28:
        font = quote_font(size)
        lines = wrap(draw, text, font, box_width)
        if len(lines) * size * 1.38 <= box_bottom - box_top:
            break
        size -= 2
    font = quote_font(size)
    lines = wrap(draw, text, font, box_width)
    line_height = size * 1.38
    max_lines = int((box_bottom - box_top) // line_height)
    if len(lines) > max_lines:
        lines = [*lines[: max_lines - 1], lines[max_lines - 1].rstrip(" .,;") + "\u2026"]
    y = box_top + (box_bottom - box_top - len(lines) * line_height) / 2
    for line in lines:
        _centered(draw, y, line, font, look.text)
        y += line_height

    draw.line((WIDTH / 2 - 70, 1050, WIDTH / 2 + 70, 1050), fill=look.accent, width=3)
    if source:
        source_font = sans(32, 600)
        for index, line in enumerate(wrap(draw, source, source_font, WIDTH - 260)[:2]):
            _centered(draw, 1074 + index * 44, line, source_font, look.soft)
    if by:
        line, size = f"{by_prefix}: {by}", 26
        while size > 18 and _text_width(draw, line, sans(size, 500)) > WIDTH - 200:
            size -= 1
        while _text_width(draw, line, sans(size, 500)) > WIDTH - 200 and len(line) > 10:
            line = line[:-2].rstrip(" ,") + "\u2026"
        _centered(draw, 1176, line, sans(size, 500), look.muted)
    _centered(draw, 1230, footer, sans(26, 700), look.accent)
    return _png(image)


def quote_card(text: str, source: str | None, saved_by: str | None, footer: str, style: str | None = None) -> bytes:
    """«💬 Iqtiboslar sandig'i»: a quote the member keeps."""
    return styled_card(
        text,
        label="Iqtiboslar sandig\u2018i",
        source=source,
        by=saved_by,
        footer=footer,
        style=style,
        by_prefix="Saqlagan",
    )


# ---------------------------------------------------------------------------- «Kitobxonlik kartam»


@dataclass
class CardData:
    name: str
    details: str
    number: str
    year: int
    tiles: list[tuple[str, str]] = field(default_factory=list)  # (value, label)
    reading_now: str | None = None
    quote: str | None = None
    footer: str = ""


def reading_card(data: CardData) -> bytes:
    image = _background()
    draw = ImageDraw.Draw(image)
    _logo(image, WIDTH // 2, 92, 100)
    _centered(draw, 206, _spaced("Kitobxonlik kartam"), sans(24, 700), GOLD)
    _centered(draw, 240, str(data.year), sans(22, 600), MUTED)

    name_font = sans(60, 800)
    while _text_width(draw, data.name, name_font) > WIDTH - 200 and name_font.size > 34:
        name_font = sans(int(name_font.size) - 2, 800)
    _centered(draw, 300, data.name, name_font, CREAM)
    detail_font = sans(28, 500)
    details = " · ".join(part for part in (data.details, data.number) if part)
    for index, line in enumerate(wrap(draw, details, detail_font, WIDTH - 220)[:2]):
        _centered(draw, 384 + index * 38, line, detail_font, MUTED)

    left, top, gap, tile_w, tile_h = 110, 480, 24, (WIDTH - 220 - 24) // 2, 150
    for index, (value, label) in enumerate(data.tiles[:6]):
        col, row = index % 2, index // 2
        x = left + col * (tile_w + gap)
        y = top + row * (tile_h + gap)
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=24, fill=NAVY700, outline=GOLD, width=2)
        value_font = sans(64, 800)
        while _text_width(draw, value, value_font) > tile_w - 40 and value_font.size > 30:
            value_font = sans(int(value_font.size) - 4, 800)
        draw.text((x + (tile_w - _text_width(draw, value, value_font)) / 2, y + 22), value, font=value_font, fill=GOLD)
        label_font = sans(24, 600)
        draw.text(
            (x + (tile_w - _text_width(draw, label, label_font)) / 2, y + 104), label, font=label_font, fill=CREAM
        )

    y = top + 3 * (tile_h + gap) + 14
    if data.reading_now:
        label_font, title_font = sans(24, 600), sans(32, 700)
        _centered(draw, y, "Hozir o‘qiyapman", label_font, MUTED)
        title = wrap(draw, data.reading_now, title_font, WIDTH - 240)[0]
        _centered(draw, y + 36, title, title_font, CREAM)
        y += 100
    if data.quote:
        quote = quote_font(30)
        lines = wrap(draw, f"“{data.quote}”", quote, WIDTH - 260)
        if len(lines) > 2:
            lines = [lines[0], lines[1].rstrip(" .,;") + "…"]
        for line in lines:
            _centered(draw, y, line, quote, GOLD300)
            y += 42
    _centered(draw, HEIGHT - 120, data.footer, sans(26, 700), GOLD)
    return _png(image)


async def reading_card_data(session: AsyncSession, user: User, footer: str) -> CardData:
    """The member's numbers for the card: this year's books and pages, the streak, points, place."""
    from app.services import ranking, reading_journal
    from app.services.passport import member_number

    stats = await reading_journal.stats(session, user)
    summary = await ranking.score_summary(session, user.id)
    board = await ranking.ranking(session, period="all", scope="all", viewer=user, limit=0)
    achievements = await session.scalar(
        select(func.count()).select_from(UserAchievement).where(UserAchievement.user_id == user.id)
    )
    faculty = (
        await session.scalar(select(Faculty.name).where(Faculty.id == user.faculty_id)) if user.faculty_id else None
    )
    course = f"{user.course}-kurs" if user.course else None
    current = (
        await session.execute(
            select(ShelfItem, Book)
            .outerjoin(Book, Book.id == ShelfItem.book_id)
            .where(ShelfItem.user_id == user.id, ShelfItem.status == ShelfStatus.READING)
            .order_by(ShelfItem.updated_at.desc())
            .limit(1)
        )
    ).first()
    quote = await session.scalar(
        select(SavedQuote.text).where(SavedQuote.user_id == user.id).order_by(SavedQuote.created_at.desc()).limit(1)
    )
    reading_now = None
    if current is not None:
        item, book = current
        reading_now = book.title if book else item.title
    place = board.me.rank if board.me else None
    return CardData(
        name=f"{user.first_name} {user.last_name}".strip(),
        details=", ".join(part for part in (faculty, course) if part),
        number=f"A’zo raqami {member_number(user)}",
        year=datetime.now(local_tz()).year,
        tiles=[
            (str(stats["finished_this_year"]), "kitob o‘qildi"),
            (f"{stats['year_pages']:,}".replace(",", " "), "bet o‘qildi"),
            (str(stats["best_streak"]), "kun ketma-ket (eng uzun)"),
            (f"{summary['total']:,}".replace(",", " "), "jami ball"),
            (f"{place}-o‘rin" if place else "—", "klub reytingida"),
            (str(int(achievements or 0)), "yutuq"),
        ],
        reading_now=reading_now,
        quote=quote[:220] if quote else None,
        footer=footer,
    )


def footer_text(bot_username: str | None) -> str:
    return f"@{bot_username} · Kitobxonlar klubi" if bot_username else "Kitobxonlar klubi"


def display(user: User) -> str:
    return f"{user.first_name} {user.last_name[:1]}." if user.last_name else user.first_name


def quote_filename(quote_id: uuid.UUID) -> str:
    return f"iqtibos-{quote_id.hex[:8]}.png"


def card_filename(user: User) -> str:
    return f"kitobxonlik-kartam-{user.member_number}.png"


def as_dict(data: CardData) -> dict[str, Any]:
    return data.__dict__
