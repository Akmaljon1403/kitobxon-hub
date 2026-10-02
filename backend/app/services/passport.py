"""«Kitobxon pasporti»: the member's ID card as a PNG image (name, faculty, stats and a QR code
that proves the card is genuine). Drawn with Pillow, so it needs no browser on the server."""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import segno
from aiogram import Bot
from PIL import Image, ImageDraw, ImageFont, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Faculty, User
from app.models.enums import AchievementCriteria, UserStatus
from app.security.crypto import constant_time_equals, keyed_hash
from app.services.storage import get_storage
from app.utils.timezone import local_tz

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1200, 756  # the shape of a bank card (85.6 x 54 mm)
FONT_DIRS = (Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/dejavu"))
GREEN_DARK = (16, 58, 41)
GREEN = (47, 111, 79)
GREEN_LIGHT = (63, 157, 110)
GOLD = (232, 192, 104)
WHITE = (255, 255, 255)
CODE_PATTERN = re.compile(r"^KH(\d{6})-([0-9A-F]{8})$")


@dataclass(frozen=True)
class PassportData:
    number: str
    first_name: str
    last_name: str
    faculty: str | None
    course: int | None
    group_name: str | None
    member_since: str
    points: int
    rank: int | None
    books: int
    events: int
    verify_url: str | None
    active: bool = True


def member_number(user: User) -> str:
    return f"KH-{user.member_number:06d}"


def verify_code(user: User) -> str:
    """Printed in the QR code; only our server can produce a valid one for a member."""
    signature = keyed_hash("passport-verify", str(user.id))[:8].upper()
    return f"KH{user.member_number:06d}-{signature}"


async def member_by_code(session: AsyncSession, code: str) -> User | None:
    match = CODE_PATTERN.match(code.strip().upper())
    if not match:
        return None
    user = await session.scalar(
        select(User).where(User.member_number == int(match.group(1)), User.deleted_at.is_(None))
    )
    if user is None or not constant_time_equals(verify_code(user), code.strip().upper()):
        return None
    return user


def verify_url(code: str) -> str | None:
    base = get_settings().base_url
    return f"{base}/v/{code}" if base else None


async def collect(session: AsyncSession, user: User) -> PassportData:
    from app.services import achievements, ranking

    faculty = (
        await session.scalar(select(Faculty.name).where(Faculty.id == user.faculty_id)) if user.faculty_id else None
    )
    summary = await ranking.score_summary(session, user.id)
    board = await ranking.ranking(session, period="all", scope="all", viewer=user, limit=1)
    progress = await achievements.progress(session, user.id)
    since = user.registered_at or user.created_at
    return PassportData(
        number=member_number(user),
        first_name=user.first_name,
        last_name=user.last_name,
        faculty=faculty,
        course=user.course,
        group_name=user.group_name,
        member_since=since.astimezone(local_tz()).strftime("%d.%m.%Y") if since else "—",
        points=summary["total"],
        rank=board.me.rank if board.me else None,
        books=progress[AchievementCriteria.BOOKS_COMPLETED],
        events=progress[AchievementCriteria.EVENTS_ATTENDED],
        verify_url=verify_url(verify_code(user)),
        active=user.status == UserStatus.ACTIVE,
    )


# ---------------------------------------------------------------------------- the photo


async def telegram_avatar(bot: Bot, user: User) -> bytes | None:
    """The member's current Telegram profile photo, fetched by the bot (cached in storage)."""
    try:
        async with asyncio.timeout(8):
            photos = await bot.get_user_profile_photos(user.telegram_id, limit=1)
            if not photos.photos:
                return None
            # The smallest size that is still sharp on the card (Telegram lists sizes small to large).
            sizes = photos.photos[0]
            size = next((s for s in sizes if min(s.width, s.height) >= 320), sizes[-1])
            key = f"avatars/{user.id}/{size.file_unique_id}.jpg"
            storage = get_storage()
            if await storage.exists(key):
                return await storage.get(key)
            telegram_file = await bot.get_file(size.file_id)
            if telegram_file.file_path is None:
                return None
            buffer = await bot.download_file(telegram_file.file_path)
            data = buffer.read() if buffer else b""
            if data:
                await storage.put(key, data, "image/jpeg")
            return data or None
    except Exception as exc:  # a missing photo must never break the passport
        logger.info("No Telegram photo for the passport of %s: %s", user.id, exc)
        return None


# ---------------------------------------------------------------------------- drawing


@lru_cache
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for folder in FONT_DIRS:
        path = folder / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def _bold(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans-Bold.ttf", size)


def _regular(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans.ttf", size)


def _mono(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSansMono-Bold.ttf", size)


def _fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, size: int, minimum: int = 18) -> ImageFont.FreeTypeFont:
    """The largest bold font (down to ``minimum``) in which ``text`` fits ``max_width``."""
    while size > minimum and draw.textlength(text, font=_bold(size)) > max_width:
        size -= 1
    return _bold(size)


def _clip(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(f"{text}…", font=font) > max_width:
        text = text[:-1]
    return f"{text.rstrip()}…"


def _spaced(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, spacing: int = 2) -> None:
    """Small capital labels look official with a little letter spacing."""
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += int(draw.textlength(char, font=font)) + spacing


def _background() -> Image.Image:
    # Diagonal gradient: dark green in the top-left corner, lighter green in the bottom-right.
    vertical = Image.linear_gradient("L").resize((WIDTH, HEIGHT))
    horizontal = (
        Image.linear_gradient("L").rotate(90).transpose(Image.Transpose.FLIP_LEFT_RIGHT).resize((WIDTH, HEIGHT))
    )
    mask = Image.blend(vertical, horizontal, 0.5)
    card = Image.composite(
        Image.new("RGB", (WIDTH, HEIGHT), GREEN_LIGHT), Image.new("RGB", (WIDTH, HEIGHT), GREEN_DARK), mask
    )
    card = card.convert("RGBA")
    pattern = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pattern)
    for radius in range(120, 900, 46):  # soft guilloche-like rings, as on official documents
        draw.ellipse(
            (WIDTH - 260 - radius, -180 - radius, WIDTH - 260 + radius, -180 + radius),
            outline=(255, 255, 255, 14),
            width=2,
        )
    for radius in range(60, 420, 38):
        draw.ellipse(
            (-140 - radius, HEIGHT + 60 - radius, -140 + radius, HEIGHT + 60 + radius),
            outline=(255, 255, 255, 10),
            width=2,
        )
    return Image.alpha_composite(card, pattern)


def _book_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    """An open book drawn with lines (the club's mark)."""
    half = size // 2
    left = [(x, y + 8), (x + half - 3, y + 16), (x + half - 3, y + size), (x, y + size - 8)]
    right = [(x + half + 3, y + 16), (x + size, y + 8), (x + size, y + size - 8), (x + half + 3, y + size)]
    draw.polygon(left, fill=GOLD)
    draw.polygon(right, fill=GOLD)
    for offset in (26, 36, 46):
        if y + offset < y + size - 10:
            draw.line((x + 8, y + offset - 4, x + half - 10, y + offset + 2), fill=GREEN_DARK, width=3)
            draw.line((x + half + 10, y + offset + 2, x + size - 8, y + offset - 4), fill=GREEN_DARK, width=3)


def _photo(avatar: bytes | None, initials: str, size: tuple[int, int]) -> Image.Image:
    width, height = size
    picture: Image.Image | None = None
    if avatar:
        try:
            picture = ImageOps.fit(Image.open(io.BytesIO(avatar)).convert("RGB"), size, Image.Resampling.LANCZOS)
        except Exception:
            picture = None
    if picture is None:
        picture = Image.new("RGB", size, (232, 241, 236))
        draw = ImageDraw.Draw(picture)
        font = _bold(104)
        box = draw.textbbox((0, 0), initials, font=font)
        draw.text(
            ((width - (box[2] - box[0])) / 2 - box[0], (height - (box[3] - box[1])) / 2 - box[1]),
            initials,
            font=font,
            fill=GREEN,
        )
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=22, fill=255)
    rounded = Image.new("RGBA", size, (0, 0, 0, 0))
    rounded.paste(picture, (0, 0), mask)
    return rounded


def _qr(url: str, size: int) -> Image.Image:
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=10, border=0, dark=GREEN_DARK, light=WHITE)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def draw_passport(data: PassportData, avatar: bytes | None = None) -> bytes:
    card = _background()
    overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    shapes = ImageDraw.Draw(overlay)
    draw = ImageDraw.Draw(card)
    soft = (255, 255, 255, 190)
    faint = (255, 255, 255, 150)

    # Header: the club's mark, the title and the membership number.
    _book_icon(draw, 48, 44, 64)
    draw.text((132, 40), "KITOBXON PASPORTI", font=_bold(44), fill=WHITE)
    draw.text(
        (134, 96), "Farg'ona jamoat salomatligi tibbiyot instituti · Kitobxonlar klubi", font=_regular(19), fill=soft
    )
    _spaced(draw, (WIDTH - 48 - 150, 30), "A'ZO RAQAMI", _regular(15), faint)
    number_font = _mono(32)
    draw.text(
        (WIDTH - 48 - draw.textlength(data.number, font=number_font), 52), data.number, font=number_font, fill=GOLD
    )
    draw.line((48, 146, WIDTH - 48, 146), fill=(*GOLD, 255), width=2)

    # Photo (Telegram profile picture or the initials) with a white frame, and the status below.
    initials = f"{data.first_name[:1]}{data.last_name[:1]}".upper() or "K"
    shapes.rounded_rectangle((42, 170, 42 + 252, 170 + 312), radius=26, fill=(255, 255, 255, 255))
    card = Image.alpha_composite(card, overlay)
    card.alpha_composite(_photo(avatar, initials, (240, 300)), (48, 176))
    draw = ImageDraw.Draw(card)
    status = "✓ FAOL A'ZO" if data.active else "A'ZOLIK TO'XTATILGAN"
    status_font = _bold(19)
    status_width = int(draw.textlength(status, font=status_font)) + 36
    draw.rounded_rectangle((48, 500, 48 + status_width, 540), radius=20, fill=GOLD if data.active else (200, 200, 200))
    draw.text((48 + 18, 509), status, font=status_font, fill=GREEN_DARK)
    draw.text((48, 556), f"Berilgan sana: {datetime.now(local_tz()):%d.%m.%Y}", font=_regular(17), fill=faint)

    # Personal details.
    left, column = 334, 412
    full = WIDTH - 48 - left

    def field(x: int, y: int, label: str, value: str, width: int, size: int = 36) -> None:
        _spaced(draw, (x, y), label, _regular(15), faint)
        font = _fit(draw, value, width, size)
        draw.text((x, y + 24), _clip(draw, value, font, width), font=font, fill=WHITE)

    field(left, 172, "FAMILIYASI", data.last_name, column - 24, 38)
    field(left + column, 172, "ISMI", data.first_name, full - column, 38)
    field(left, 262, "FAKULTET", data.faculty or "—", full, 30)
    field(left, 344, "KURS", f"{data.course}-kurs" if data.course else "—", 170, 30)
    field(left + 200, 344, "GURUH", data.group_name or "—", 190, 30)
    field(left + column, 344, "A'ZO BO'LGAN", data.member_since, full - column, 30)

    # Statistics strip.
    stats = [
        (f"{data.points:,}".replace(",", " "), "ball"),
        (f"{data.rank}-o'rin" if data.rank else "—", "reyting"),
        (str(data.books), "kitob o'qigan"),
        (str(data.events), "tadbirda"),
    ]
    gap = 14
    tile = (full - gap * 3) // 4
    overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    shapes = ImageDraw.Draw(overlay)
    for index in range(4):
        x = left + index * (tile + gap)
        shapes.rounded_rectangle((x, 438, x + tile, 548), radius=18, fill=(255, 255, 255, 34))
    card = Image.alpha_composite(card, overlay)
    draw = ImageDraw.Draw(card)
    for index, (value, label) in enumerate(stats):
        x = left + index * (tile + gap)
        font = _fit(draw, value, tile - 24, 38, 20)
        draw.text((x + tile / 2, 482), value, font=font, fill=WHITE, anchor="mm")
        draw.text((x + tile / 2, 524), label, font=_regular(17), fill=soft, anchor="mm")

    # Footer: what the card is and the verification QR code.
    draw.text((left, 600), "Ushbu pasport Kitobxonlar klubi a'zoligini tasdiqlaydi.", font=_regular(19), fill=soft)
    draw.text((left, 630), "Haqiqiyligini QR kod orqali tekshirish mumkin.", font=_regular(19), fill=faint)
    if data.verify_url:
        qr_size = 136
        x, y = WIDTH - 48 - qr_size, HEIGHT - 40 - qr_size
        draw.rounded_rectangle((x - 10, y - 10, x + qr_size + 10, y + qr_size + 10), radius=14, fill=WHITE)
        card.paste(_qr(data.verify_url, qr_size), (x, y))

    output = io.BytesIO()
    card.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


async def render(session: AsyncSession, user: User, *, bot: Bot | None = None) -> bytes:
    """The passport image; with ``bot`` the member's Telegram photo is printed on it."""
    data = await collect(session, user)
    avatar = await telegram_avatar(bot, user) if bot is not None else None
    return await asyncio.to_thread(draw_passport, data, avatar)


def filename(user: User) -> str:
    return f"kitobxon-pasporti-{member_number(user)}.png"
