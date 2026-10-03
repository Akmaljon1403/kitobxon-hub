"""«Kitobxon pasporti»: the member's ID card as a PNG image (photo, name, faculty, membership
number and a QR code). Results change every day, so they are not printed: the QR code opens a page
with the live points, ranking and achievements, which also proves the card is genuine.
Drawn with Pillow, so it needs no browser on the server."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import segno
from aiogram import Bot
from PIL import Image, ImageDraw, ImageFont, ImageOps
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, BadRequestError, ForbiddenError
from app.models import Faculty, User
from app.models.enums import AchievementCriteria, UserStatus
from app.security.crypto import constant_time_equals, keyed_hash
from app.services.settings import get_setting
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
    verify_url: str | None
    active: bool = True
    premium: bool = False  # the «Premium a'zo» badge
    theme: str = "classic"  # see THEMES; premium members choose
    organization: str = "Farg'ona jamoat salomatligi tibbiyot instituti · Kitobxonlar klubi"


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
    from app.services import premium as premium_service

    faculty = (
        await session.scalar(select(Faculty.name).where(Faculty.id == user.faculty_id)) if user.faculty_id else None
    )
    since = user.registered_at or user.created_at
    premium = await premium_service.is_premium(session, user.id)
    return PassportData(
        number=member_number(user),
        first_name=user.first_name,
        last_name=user.last_name,
        faculty=faculty,
        course=user.course,
        group_name=user.group_name,
        member_since=since.astimezone(local_tz()).strftime("%d.%m.%Y") if since else "—",
        verify_url=verify_url(verify_code(user)),
        active=user.status == UserStatus.ACTIVE,
        premium=premium,
        theme=effective_theme(user.passport_theme, premium),
        organization=" · ".join(
            [await get_setting(session, "org.organization_name"), await get_setting(session, "org.club_name")]
        ),
    )


async def live_results(session: AsyncSession, user: User) -> dict[str, Any]:
    """What changes every day; shown on the page behind the QR code instead of on the card."""
    from app.models import Certificate, UserAchievement
    from app.services import achievements, ranking
    from app.services import premium as premium_service

    summary = await ranking.score_summary(session, user.id)
    board = await ranking.ranking(session, period="all", scope="all", viewer=user, limit=1)
    monthly = await ranking.ranking(session, period="month", scope="all", viewer=user, limit=1)
    progress = await achievements.progress(session, user.id)
    certificates = list(
        await session.scalars(
            select(Certificate.title)
            .where(Certificate.user_id == user.id, Certificate.revoked_at.is_(None))
            .order_by(Certificate.issued_at.desc())
            .limit(5)
        )
    )
    unlocked = await session.scalar(
        select(func.count()).select_from(UserAchievement).where(UserAchievement.user_id == user.id)
    )
    return {
        "points": summary["total"],
        "rank": board.me.rank if board.me else None,
        "month_rank": monthly.me.rank if monthly.me else None,
        "books": progress[AchievementCriteria.BOOKS_COMPLETED],
        "events": progress[AchievementCriteria.EVENTS_ATTENDED],
        "tests": progress[AchievementCriteria.TESTS_PASSED],
        "achievements": int(unlocked or 0),
        "certificates": certificates,
        "premium": await premium_service.is_premium(session, user.id),
    }


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


@dataclass(frozen=True)
class Theme:
    title: str
    light: tuple[int, int, int]  # bottom-right of the gradient
    dark: tuple[int, int, int]  # top-left of the gradient
    accent: tuple[int, int, int]  # the line, the number, the badge and the book mark
    ring: tuple[int, int, int, int]  # the guilloche rings
    frame: tuple[int, int, int] | None = None  # an outer frame (premium designs)
    premium: bool = True


THEMES: dict[str, Theme] = {
    "classic": Theme("Klassik yashil", (63, 157, 110), (16, 58, 41), GOLD, (255, 255, 255, 14), premium=False),
    "gold": Theme("Oltin", (24, 92, 66), (8, 36, 26), GOLD, (*GOLD, 34), GOLD),
    "midnight": Theme("Tungi ko'k", (44, 78, 150), (10, 20, 48), (205, 216, 236), (205, 216, 236, 26), (205, 216, 236)),
    "ruby": Theme("Yoqut", (150, 36, 66), (50, 10, 24), GOLD, (*GOLD, 28), GOLD),
}


def effective_theme(user_choice: str | None, premium: bool) -> str:
    """Premium members keep their chosen design (gold by default); everyone else gets the classic one."""
    if not premium:
        return "classic"
    return user_choice if user_choice in THEMES else "gold"


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


def _serif(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSerif.ttf", size)


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


def _background(theme: Theme) -> Image.Image:
    # Diagonal gradient: dark in the top-left corner, lighter in the bottom-right.
    vertical = Image.linear_gradient("L").resize((WIDTH, HEIGHT))
    horizontal = (
        Image.linear_gradient("L").rotate(90).transpose(Image.Transpose.FLIP_LEFT_RIGHT).resize((WIDTH, HEIGHT))
    )
    mask = Image.blend(vertical, horizontal, 0.5)
    card = Image.composite(
        Image.new("RGB", (WIDTH, HEIGHT), theme.light), Image.new("RGB", (WIDTH, HEIGHT), theme.dark), mask
    ).convert("RGBA")
    pattern = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pattern)
    for radius in range(120, 900, 46):  # soft guilloche-like rings, as on official documents
        draw.ellipse(
            (WIDTH - 260 - radius, -180 - radius, WIDTH - 260 + radius, -180 + radius), outline=theme.ring, width=2
        )
    for radius in range(60, 420, 38):
        draw.ellipse(
            (-140 - radius, HEIGHT + 60 - radius, -140 + radius, HEIGHT + 60 + radius),
            outline=(255, 255, 255, 10),
            width=2,
        )
    if theme.frame:
        draw.rounded_rectangle((12, 12, WIDTH - 13, HEIGHT - 13), radius=26, outline=(*theme.frame, 255), width=4)
    return Image.alpha_composite(card, pattern)


def _book_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, theme: Theme) -> None:
    """An open book drawn with lines (the club's mark)."""
    half = size // 2
    left = [(x, y + 8), (x + half - 3, y + 16), (x + half - 3, y + size), (x, y + size - 8)]
    right = [(x + half + 3, y + 16), (x + size, y + 8), (x + size, y + size - 8), (x + half + 3, y + size)]
    draw.polygon(left, fill=theme.accent)
    draw.polygon(right, fill=theme.accent)
    for offset in (26, 36, 46):
        if y + offset < y + size - 10:
            draw.line((x + 8, y + offset - 4, x + half - 10, y + offset + 2), fill=theme.dark, width=3)
            draw.line((x + half + 10, y + offset + 2, x + size - 8, y + offset - 4), fill=theme.dark, width=3)


def _photo(avatar: bytes | None, initials: str, size: tuple[int, int], theme: Theme) -> Image.Image:
    width, height = size
    picture: Image.Image | None = None
    if avatar:
        try:
            picture = ImageOps.fit(
                Image.open(io.BytesIO(avatar)).convert("RGB"), size, Image.Resampling.LANCZOS, centering=(0.5, 0.35)
            )
        except Exception:
            picture = None
    if picture is None:
        picture = Image.new("RGB", size, (236, 242, 239))
        draw = ImageDraw.Draw(picture)
        font = _bold(112)
        box = draw.textbbox((0, 0), initials, font=font)
        draw.text(
            ((width - (box[2] - box[0])) / 2 - box[0], (height - (box[3] - box[1])) / 2 - box[1]),
            initials,
            font=font,
            fill=theme.dark,
        )
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=22, fill=255)
    rounded = Image.new("RGBA", size, (0, 0, 0, 0))
    rounded.paste(picture, (0, 0), mask)
    return rounded


def _qr(url: str, size: int, color: tuple[int, int, int]) -> Image.Image:
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=10, border=0, dark=color, light=WHITE)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB").resize((size, size), Image.Resampling.NEAREST)


def draw_passport(data: PassportData, avatar: bytes | None = None) -> bytes:
    """Only lasting details are printed; live results (points, ranking) open from the QR code."""
    theme = THEMES.get(data.theme, THEMES["classic"])
    card = _background(theme)
    draw = ImageDraw.Draw(card)
    soft = (255, 255, 255, 190)
    faint = (255, 255, 255, 150)

    # Header: the club's mark, the title and the membership number.
    _book_icon(draw, 48, 44, 64, theme)
    draw.text((132, 40), "KITOBXON PASPORTI", font=_bold(44), fill=WHITE)
    subtitle_font = _regular(19)
    draw.text(
        (134, 96), _clip(draw, data.organization, subtitle_font, WIDTH - 48 - 200 - 134), font=subtitle_font, fill=soft
    )
    _spaced(draw, (WIDTH - 48 - 150, 30), "A'ZO RAQAMI", _regular(15), faint)
    number_font = _mono(32)
    draw.text(
        (WIDTH - 48 - draw.textlength(data.number, font=number_font), 52),
        data.number,
        font=number_font,
        fill=theme.accent,
    )
    draw.line((48, 146, WIDTH - 48, 146), fill=(*theme.accent, 255), width=2)

    # Photo (the member's own, the Telegram picture or the initials) in a white frame.
    initials = f"{data.first_name[:1]}{data.last_name[:1]}".upper() or "K"
    overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rounded_rectangle((42, 170, 42 + 276, 170 + 342), radius=26, fill=(255, 255, 255, 255))
    card = Image.alpha_composite(card, overlay)
    card.alpha_composite(_photo(avatar, initials, (264, 330), theme), (48, 176))
    draw = ImageDraw.Draw(card)
    status = ("★ PREMIUM A'ZO" if data.premium else "✓ FAOL A'ZO") if data.active else "A'ZOLIK TO'XTATILGAN"
    status_font = _bold(19)
    status_width = int(draw.textlength(status, font=status_font)) + 36
    draw.rounded_rectangle(
        (48, 532, 48 + status_width, 572), radius=20, fill=theme.accent if data.active else (200, 200, 200)
    )
    draw.text((48 + 18, 541), status, font=status_font, fill=theme.dark)
    draw.text((48, 590), f"Berilgan sana: {datetime.now(local_tz()):%d.%m.%Y}", font=_regular(17), fill=faint)

    # Personal details: only what does not change from day to day.
    left, column = 360, 400
    full = WIDTH - 48 - left

    def field(x: int, y: int, label: str, value: str, width: int, size: int = 36) -> None:
        _spaced(draw, (x, y), label, _regular(15), faint)
        font = _fit(draw, value, width, size)
        draw.text((x, y + 24), _clip(draw, value, font, width), font=font, fill=WHITE)

    field(left, 176, "FAMILIYASI", data.last_name, column - 24, 40)
    field(left + column, 176, "ISMI", data.first_name, full - column, 40)
    field(left, 272, "FAKULTET", data.faculty or "—", full, 30)
    field(left, 358, "KURS", f"{data.course}-kurs" if data.course else "—", 170, 30)
    field(left + 200, 358, "GURUH", data.group_name or "—", 180, 30)
    field(left + column, 358, "A'ZO BO'LGAN", data.member_since, full - column, 30)

    # The club's motto between two thin lines.
    draw.line((left, 452, WIDTH - 48, 452), fill=(255, 255, 255, 60), width=1)
    draw.text((left, 470), "«Kitob — aql chirog'i, bilim kaliti»", font=_serif(26), fill=(*theme.accent, 255))
    draw.line((left, 520, WIDTH - 48, 520), fill=(255, 255, 255, 60), width=1)

    # Footer: what the card is, and the QR code that opens live results and verification.
    draw.text((left, 566), "Ushbu pasport Kitobxonlar klubi a'zoligini tasdiqlaydi.", font=_regular(19), fill=soft)
    draw.text((left, 596), "Ball, reyting va yutuqlar — QR kodni skanerlang.", font=_regular(19), fill=faint)
    if data.verify_url:
        qr_size = 150
        x, y = WIDTH - 48 - qr_size, HEIGHT - 40 - qr_size
        draw.rounded_rectangle((x - 10, y - 10, x + qr_size + 10, y + qr_size + 10), radius=14, fill=WHITE)
        card.paste(_qr(data.verify_url, qr_size, theme.dark), (x, y))

    output = io.BytesIO()
    card.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


# ---------------------------------------------------------------------------- the member's own photo

MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTO_PIXELS = 40_000_000
PHOTO_SIZE = (480, 600)  # 4:5, like a document photo


def prepare_photo(data: bytes) -> bytes:
    """Check an uploaded picture, turn it upright, crop it to 4:5 and drop its metadata (GPS...)."""
    from PIL import UnidentifiedImageError

    if not data or len(data) > MAX_PHOTO_BYTES:
        raise BadRequestError("PHOTO_TOO_LARGE", "Rasm 10 MB dan oshmasin.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > MAX_PHOTO_PIXELS:
            raise BadRequestError("PHOTO_TOO_LARGE", "Rasm o'lchami juda katta.")
        image.verify()
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise BadRequestError("PHOTO_INVALID", "Bu fayl rasm emas yoki buzilgan. JPG yoki PNG yuboring.") from exc
    picture = ImageOps.fit(image, PHOTO_SIZE, Image.Resampling.LANCZOS, centering=(0.5, 0.35))
    output = io.BytesIO()
    picture.save(output, format="JPEG", quality=88)
    return output.getvalue()


async def set_photo(session: AsyncSession, user: User, data: bytes) -> None:
    prepared = await asyncio.to_thread(prepare_photo, data)
    storage = get_storage()
    old = user.passport_photo_key
    key = f"passport-photos/{user.id}/{uuid.uuid4().hex}.jpg"
    await storage.put(key, prepared, "image/jpeg")
    user.passport_photo_key = key
    await session.commit()
    if old:
        try:
            await storage.delete(old)
        except AppError:
            pass


async def clear_photo(session: AsyncSession, user: User) -> None:
    """Back to the Telegram profile picture (also used by admins for an unsuitable photo)."""
    old = user.passport_photo_key
    user.passport_photo_key = None
    await session.commit()
    if old:
        try:
            await get_storage().delete(old)
        except AppError:
            pass


async def own_photo(user: User) -> bytes | None:
    if not user.passport_photo_key:
        return None
    try:
        return await get_storage().get(user.passport_photo_key)
    except AppError:
        return None  # lost file (e.g. a rebuilt free server): fall back to the Telegram picture


async def set_theme(session: AsyncSession, user: User, theme: str) -> None:
    from app.services import premium as premium_service

    if theme not in THEMES:
        raise BadRequestError("THEME_UNKNOWN", "Bunday dizayn yo'q.")
    if theme != "classic" and not await premium_service.is_premium(session, user.id):
        raise ForbiddenError("PREMIUM_REQUIRED", "Pasport dizaynlari — Premium a'zolar uchun.")
    user.passport_theme = theme
    await session.commit()


async def render(session: AsyncSession, user: User, *, bot: Bot | None = None) -> bytes:
    """The passport image: the member's own photo, else (with ``bot``) the Telegram picture."""
    data = await collect(session, user)
    avatar = await own_photo(user)
    if avatar is None and bot is not None:
        avatar = await telegram_avatar(bot, user)
    return await asyncio.to_thread(draw_passport, data, avatar)


def filename(user: User) -> str:
    return f"kitobxon-pasporti-{member_number(user)}.png"
