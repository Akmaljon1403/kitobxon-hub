"""Posts in the club's Telegram channel (e.g. @FJSTIMutolaaxona), published by the bot as a
channel administrator.

Automatic posts (each can be switched off in Settings → channel):
* a new event — with the book to read for it («falon kuni falon soatga mana bu kitobni o'qib kelamiz»);
* event reminders the day before and on the day;
* a new book, and reading nudges halfway and three days before the deadline
  («asarni tugatay deb qoldingizmi, kitobxonlar?»);
* the quote of the day;
* results: test winners, giveaway winners, the month's leaders;
* a weekly invitation to join the bot.

Every post ends with a button that opens the bot and, if admins saved some with /stiker, a
sticker. Posts are queued in ``channel_posts`` (one per business fact, by dedup key), moved out
of the night hours and sent by the background worker (``app.workers.sender``).
"""

from __future__ import annotations

import html
import io
import random
import re
import uuid
import zlib
from datetime import UTC, datetime, time, timedelta
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Book, BookQuote, ChannelPost, ChannelSticker, Event, Test, User
from app.models.enums import (
    BookStatus,
    ChannelPostKind,
    ChannelPostStatus,
    EventStatus,
    NotificationType,
    StickerMood,
    UserStatus,
)
from app.services.audit import record_audit
from app.services.notifications import wake_sender
from app.services.settings import get_setting
from app.services.stickers import mood_for
from app.utils.timezone import MONTHS_UZ, format_human_date, local_tz

# Posts never go out at night (club time zone): they wait for the morning.
DAYTIME = (time(8, 0), time(21, 30))
MORNING = time(9, 0)
JOIN_BUTTON = {"text": "📲 Botga qo'shilish", "bot_start": "channel"}
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
WEEKDAYS = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba")
MONTHLY_SINCE = "2026-10"
TOGGLES = {
    ChannelPostKind.EVENT: "channel.post_events",
    ChannelPostKind.EVENT_REMINDER: "channel.post_events",
    ChannelPostKind.BOOK: "channel.post_books",
    ChannelPostKind.READING_NUDGE: "channel.post_books",
    ChannelPostKind.QUOTE: "channel.post_quotes",
    ChannelPostKind.RESULTS: "channel.post_results",
    ChannelPostKind.INVITE: "channel.post_invites",
    ChannelPostKind.REPORT: "channel.post_reports",
}


def _e(value: Any) -> str:
    return html.escape(str(value), quote=False)


def _pick(variants: tuple[str, ...], key: str) -> str:
    """A stable choice among text variants, so posts do not all sound the same."""
    return variants[zlib.crc32(key.encode()) % len(variants)]


def normalize_chat_id(value: str) -> str | int | None:
    """«@name», «t.me/name», «https://t.me/name» → «@name»; «-100123» → the number."""
    text = (value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    match = re.fullmatch(r"(?:https?://)?(?:t\.me/|telegram\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})/?", text)
    return f"@{match.group(1)}" if match else None


def parse_targets(raw: str) -> list[dict[str, str]]:
    """«Ustozlar=@kanalB, @kanalC» → [{"chat_id": "@kanalB", "title": "Ustozlar"}, ...].

    Each entry is an optional display name and a channel address (@username or a -100… id), separated by «=».
    Invalid or duplicate addresses are skipped, so a typo never breaks the destinations list."""
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in (raw or "").split(","):
        title, sep, address = item.strip().partition("=")
        if not sep:
            title, address = "", title
        chat = normalize_chat_id(address)
        if chat is None:
            continue
        chat_str = str(chat)
        if chat_str in seen:
            continue
        seen.add(chat_str)
        result.append({"chat_id": chat_str, "title": title.strip() or chat_str})
    return result


async def _primary_chat(session: AsyncSession) -> str | int | None:
    return normalize_chat_id(str(await get_setting(session, "channel.chat_id")))


async def destinations(session: AsyncSession) -> list[dict[str, Any]]:
    """Channels a manual post may go to: the primary club channel first, then any extra ones
    (``channel.extra_targets``). «📢 Xabarlar» lists these as «qayerga yuborish» choices."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    primary = await _primary_chat(session)
    if primary is not None:
        seen.add(str(primary))
        result.append({"chat_id": str(primary), "title": str(primary), "primary": True})
    for extra in parse_targets(str(await get_setting(session, "channel.extra_targets"))):
        if extra["chat_id"] in seen:
            continue
        seen.add(extra["chat_id"])
        result.append({"chat_id": extra["chat_id"], "title": extra["title"], "primary": False})
    return result


def next_daytime(when: datetime) -> datetime:
    """``when`` if it is daytime in the club, otherwise the next morning at 09:00."""
    local = when.astimezone(local_tz())
    if DAYTIME[0] <= local.time() <= DAYTIME[1]:
        return when
    day = local.date() if local.time() < DAYTIME[0] else local.date() + timedelta(days=1)
    return datetime.combine(day, MORNING, tzinfo=local_tz()).astimezone(UTC)


def _weekday_date(value: datetime) -> str:
    local = value.astimezone(local_tz())
    return f"{WEEKDAYS[local.weekday()].capitalize()}, {local.day}-{MONTHS_UZ[local.month - 1]}"


def prepare_image(data: bytes) -> bytes:
    """Check an uploaded picture and keep a JPEG copy without metadata (GPS etc.)."""
    if not data or len(data) > 10 * 1024 * 1024:
        raise BadRequestError("IMAGE_TOO_LARGE", "Rasm 10 MB dan oshmasin.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 40_000_000:
            raise BadRequestError("IMAGE_TOO_LARGE", "Rasm o'lchami juda katta.")
        image.verify()
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise BadRequestError("IMAGE_INVALID", "Rasm faylini tanlang (JPG yoki PNG).") from exc
    image.thumbnail((1920, 1920))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88)
    return output.getvalue()


async def is_on(session: AsyncSession, kind: ChannelPostKind | None = None) -> bool:
    if not await get_setting(session, "channel.enabled"):
        return False
    if normalize_chat_id(str(await get_setting(session, "channel.chat_id"))) is None:
        return False
    toggle = TOGGLES.get(kind) if kind else None
    return bool(await get_setting(session, toggle)) if toggle else True


POST_MOODS = {
    ChannelPostKind.RESULTS: StickerMood.CELEBRATE,
    ChannelPostKind.BOOK: StickerMood.READING,
    ChannelPostKind.READING_NUDGE: StickerMood.READING,
    ChannelPostKind.QUOTE: StickerMood.READING,
    ChannelPostKind.INVITE: StickerMood.WELCOME,
}


async def _random_sticker(session: AsyncSession, kind: ChannelPostKind) -> str | None:
    """A saved sticker that suits the post (a celebrating one under results, a reading one under books)."""
    if not await get_setting(session, "channel.stickers"):
        return None
    rows = (await session.execute(select(ChannelSticker.mood, ChannelSticker.file_id))).all()
    wanted = POST_MOODS.get(kind, StickerMood.ANY)
    choices = [file_id for mood, file_id in rows if mood == wanted] or [
        file_id for mood, file_id in rows if mood == StickerMood.ANY
    ]
    return random.choice(choices or [file_id for _, file_id in rows]) if rows else None  # noqa: S311


async def queue(
    session: AsyncSession,
    *,
    kind: ChannelPostKind,
    text: str,
    dedup_key: str | None = None,
    photo_key: str | None = None,
    photo_url: str | None = None,
    buttons: list[dict[str, Any]] | None = None,
    sticker_file_id: str | None = None,
    scheduled_at: datetime | None = None,
    created_by: uuid.UUID | None = None,
    automatic: bool = True,
    extra_photos: list[str] | None = None,
) -> bool:
    """Queue a post. Automatic posts respect the switches, the night hours and get a sticker.
    Returns False when nothing was queued (switched off or already posted)."""
    if automatic and not await is_on(session, kind):
        return False
    when = scheduled_at or datetime.now(UTC)
    if automatic:
        # The admins get a few minutes to look at it first (see ``request_reviews``).
        when = next_daytime(when + timedelta(minutes=await review_minutes(session)))
        sticker_file_id = sticker_file_id or await _random_sticker(session, kind)
    statement = (
        insert(ChannelPost)
        .values(
            kind=kind,
            text=text.strip(),
            dedup_key=dedup_key,
            photo_key=photo_key,
            photo_url=photo_url,
            extra_photo_keys=extra_photos or None,
            buttons=buttons if buttons is not None else [JOIN_BUTTON],
            sticker_file_id=sticker_file_id,
            scheduled_at=when,
            created_by=created_by,
        )
        .on_conflict_do_nothing(index_elements=[ChannelPost.dedup_key])
        .returning(ChannelPost.id)
    )
    created = await session.scalar(statement)
    if created is not None:
        wake_sender()
    return created is not None


# ---------------------------------------------------------------------------- business events


async def _book(session: AsyncSession, book_id: uuid.UUID | None) -> Book | None:
    if book_id is None:
        return None
    book = await session.get(Book, book_id)
    return book if book is not None and book.deleted_at is None else None


def event_button(event: Event) -> dict[str, Any]:
    """Opens the bot on this very event: one tap registers the member (or starts registration)."""
    return {"text": "✅ Qatnashaman", "bot_start": f"ev_{event.id.hex}"}


async def _event_post(session: AsyncSession, event: Event, shifts: list[Any]) -> tuple[str, Book | None]:
    from app.services import event_times

    book = await _book(session, event.book_id)
    title = _e(event.title)
    lines = [
        _pick(
            (
                f"📅 <b>Yangi tadbir — «{title}»!</b>",
                f"🎉 <b>Kitobxonlar, uchrashamiz: «{title}»!</b>",
                f"📣 <b>Diqqat! «{title}» tadbiri e'lon qilindi</b>",
            ),
            f"event:{event.id}",
        ),
        "",
        f"🗓 <b>Qachon:</b> {_e(event_times.when_text(event, shifts))}",
    ]
    if event.location:
        lines.append(f"📍 <b>Qayerda:</b> {_e(event.location)}")
    # The start and when attendance opens, stated plainly — the heart of the announcement.
    if shifts:
        lines.append("✅ <b>Davomat</b> har smena boshlanishidan ~10 daqiqa oldin ochiladi (QR kod bilan).")
    else:
        opens = event.attendance_opens_at.astimezone(local_tz())
        lines.append(f"✅ <b>Davomat</b> soat {opens:%H:%M} dan ochiladi (QR kod bilan).")
    if book is not None:
        lines += ["", f"📚 <b>Mavzu:</b> «{_e(book.title)}» — {_e(book.author)}. Asarni o'qib keling!"]
    if event.description:
        lines += ["", _e(event.description.strip()[:600])]
    lines += [
        "",
        "🏅 Faol qatnashchilarga ball, g'oliblarga sertifikat va sovg'alar.",
        "✋ <b>Kelmoqchimisiz?</b> Pastdagi «✅ Qatnashaman» tugmasini bosing"
        + (" va smenangizni tanlang" if shifts else "")
        + " — eslatma yuboramiz, joyni tayyorlaymiz.",
    ]
    return "\n".join(lines), book


async def event_announced(session: AsyncSession, event: Event) -> bool:
    from app.services.events import shifts_of

    if event.status != EventStatus.PUBLISHED or event.starts_at <= datetime.now(UTC):
        return False
    text, book = await _event_post(session, event, await shifts_of(session, event.id))
    return await queue(
        session,
        kind=ChannelPostKind.EVENT,
        text=text,
        dedup_key=f"event:{event.id}",
        photo_key=book.cover_key if book is not None else None,
        photo_url=book.cover_url if book is not None and not book.cover_key else None,
        buttons=[event_button(event)],
    )


async def event_changed(session: AsyncSession, event: Event, shifts: list[Any]) -> bool:
    """A post not sent yet gets the new time; an announcement already out gets a short update post."""
    from app.services import event_times

    pending = await session.scalar(
        select(ChannelPost).where(
            ChannelPost.dedup_key == f"event:{event.id}", ChannelPost.status == ChannelPostStatus.PENDING
        )
    )
    if pending is not None:
        pending.text, book = await _event_post(session, event, shifts)
        pending.photo_key = book.cover_key if book is not None else None
        pending.photo_url = book.cover_url if book is not None and not book.cover_key else None
        return True
    announced = await session.scalar(
        select(ChannelPost.id).where(
            ChannelPost.dedup_key == f"event:{event.id}", ChannelPost.status == ChannelPostStatus.SENT
        )
    )
    if announced is None:
        return await event_announced(session, event)
    lines = [
        "🔔 <b>Diqqat, o'zgarish!</b>",
        "",
        f"<b>«{_e(event.title)}»</b> tadbiri endi:",
        f"🗓 {_e(event_times.when_text(event, shifts))}",
    ]
    if event.location:
        lines.append(f"📍 {_e(event.location)}")
    lines += [
        "",
        "Ro'yxatdan o'tganlarga eslatmani yangi vaqtga yuboramiz. Hali yozilmagan bo'lsangiz — pastdagi tugma 👇",
    ]
    return await queue(
        session,
        kind=ChannelPostKind.EVENT_REMINDER,
        text="\n".join(lines),
        dedup_key=f"event_change:{event.id}:{event_times.stamp(event.starts_at)}",
        buttons=[event_button(event)],
    )


async def event_cancelled(session: AsyncSession, event: Event) -> bool:
    """Posts about the event that have not gone out are dropped; an announced event gets a short note."""
    pending = list(
        await session.scalars(
            select(ChannelPost).where(
                ChannelPost.status == ChannelPostStatus.PENDING,
                or_(
                    ChannelPost.dedup_key == f"event:{event.id}",
                    ChannelPost.dedup_key.like(f"event_reminder:{event.id}:%"),
                    ChannelPost.dedup_key.like(f"event_change:{event.id}:%"),
                ),
            )
        )
    )
    for post in pending:
        post.status = ChannelPostStatus.CANCELLED
        post.last_error = "tadbir bekor qilindi"
    announced = await session.scalar(
        select(ChannelPost.id).where(
            ChannelPost.dedup_key == f"event:{event.id}", ChannelPost.status == ChannelPostStatus.SENT
        )
    )
    if announced is None:
        return False
    return await queue(
        session,
        kind=ChannelPostKind.EVENT_REMINDER,
        text=f"❌ <b>«{_e(event.title)}»</b> tadbiri bekor qilindi.\n\n"
        "Noqulaylik uchun uzr — yangi uchrashuvni albatta e'lon qilamiz 📚",
        dedup_key=f"event_cancel:{event.id}",
        buttons=[],
    )


BOOK_HOOKS = (
    "📚 <b>Yangi sahifa ochiladi!</b> Bu safar qaysi olamga sayohat qilamiz?",
    "✨ <b>Kitobxonlar, navbatdagi asar tanlandi!</b>",
    "🔖 <b>Bir kitob — ming savol, ming javob.</b> Navbatdagi asarimiz bilan tanishing:",
    "☕ <b>Choyingizni damlab qo'ying</b> — yangi kitob vaqti keldi!",
    "🌙 <b>Ehtiyot bo'ling: bu kitob tunlari uyg'oq ushlab turishi mumkin...</b>",
    "🗝 <b>Har bir kitob — yangi eshik.</b> Bu safargi kalit sizning qo'lingizda:",
)
BOOK_ENDINGS = (
    "Birga o'qiymiz, birga muhokama qilamiz — marra hammamizniki! 💪",
    "Kitob — eng sodiq do'st. Bu do'st bilan tanishishni kechiktirmang 📖",
    "Sahifalar sizni kutyapti. Birinchi qadam — bugun! 🚀",
    "Kuniga 20 daqiqa — va kitob tugaydi. Boshladikmi? 📚",
    "Har bir sahifa — yangi fikr. O'qing, belgilang, ball to'plang 🏆",
    "O'qiganlaringizni tadbirda muhokama qilamiz — fikringizni tayyorlab qo'ying ☕",
)


# The phrase lists the owner can rewrite in the Admin Panel («📝 Matnlar» → «📣 Kanal postlari»):
# (title, the built-in phrases, what each phrase may contain).
EDITABLE: dict[str, tuple[str, tuple[str, ...], str]] = {}


def _editable(key: str, title: str, phrases: tuple[str, ...], hint: str = "") -> None:
    EDITABLE[key] = (title, phrases, hint)


def phrases(key: str) -> tuple[str, ...]:
    """The phrases in use: the owner's own, or the built-in ones."""
    from app.bot import text_store

    return text_store.options(key, EDITABLE[key][1])


_editable("channel.book_hooks", "Yangi kitob posti — boshlanish jumlasi", BOOK_HOOKS)
_editable("channel.book_endings", "Yangi kitob posti — yakunlovchi jumla", BOOK_ENDINGS)


def book_button(book: Book) -> dict[str, Any]:
    return {"text": "📖 O'qiyman", "bot_start": f"bk_{book.id.hex}"}


async def book_announced(session: AsyncSession, book: Book) -> bool:
    from app.services import literary

    if book.status != BookStatus.ACTIVE or book.deleted_at is not None:
        return False
    key = f"book:{book.id}"
    lines = [_pick(phrases("channel.book_hooks"), key), "", f"📖 <b>«{_e(book.title)}»</b>", f"✍️ {_e(book.author)}"]
    if book.description:
        lines += ["", _e(book.description.strip()[:450])]
    quote = await literary.book_line(session, book.id, key)
    if quote:
        lines += ["", f"💬 {quote}"]
    details = []
    today = datetime.now(UTC).astimezone(local_tz()).date()
    start = book.start_date if book.start_date and book.start_date > today else today
    if book.deadline:
        days = (book.deadline - start).days
        details.append(
            f"🗓 O'qish muddati: {format_human_date(book.deadline)} gacha" + (f" ({days} kun)" if days > 0 else "")
        )
        if book.pages and days > 0:
            per_day = max(1, -(-book.pages // days))
            details.append(f"📄 {book.pages} bet — kuniga atigi ~{per_day} bet")
    elif book.pages:
        details.append(f"📄 {book.pages} bet")
    if details:
        lines += ["", *details]
    lines += [
        "",
        "🏅 O'qib tugatganlarga — ball, testda g'oliblarga — sertifikat.",
        "👇 «📖 O'qiyman» tugmasini bosing — eslatma va maslahatlar bilan birga marraga yetamiz!",
        "",
        _pick(phrases("channel.book_endings"), key + ":end"),
    ]
    return await queue(
        session,
        kind=ChannelPostKind.BOOK,
        text="\n".join(lines),
        dedup_key=key,
        photo_key=book.cover_key,
        photo_url=book.cover_url if not book.cover_key else None,
        buttons=[book_button(book)],
    )


async def _names(session: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    from app.services.ranking import display_name

    name_format = str(await get_setting(session, "ranking.public_name_format"))
    users = await session.scalars(select(User).where(User.id.in_(user_ids))) if user_ids else []
    return {user.id: display_name(user.first_name, user.last_name or "", name_format) for user in users}


async def test_winners(session: AsyncSession, test: Test, standings: list[dict[str, Any]]) -> bool:
    top = standings[:3]
    if not top:
        return False
    names = await _names(session, [row["user_id"] for row in top])
    lines = [f"🏆 <b>«{_e(test.title)}» testi natijalari</b>", ""]
    for row in top:
        lines.append(
            f"{MEDALS[row['place']]} {_e(names.get(row['user_id'], '—'))} — {row['score']}/{test.max_score} ball"
        )
    lines += ["", "G'oliblarni tabriklaymiz! 🎉 Keyingi testda siz ham shu ro'yxatda bo'lishingiz mumkin."]
    return await queue(session, kind=ChannelPostKind.RESULTS, text="\n".join(lines), dedup_key=f"test:{test.id}")


async def giveaway_results(session: AsyncSession, giveaway_id: uuid.UUID, text: str) -> bool:
    """``text`` is the plain announcement already sent to members."""
    return await queue(session, kind=ChannelPostKind.RESULTS, text=_e(text), dedup_key=f"giveaway:{giveaway_id}")


async def quote_posted(session: AsyncSession, quote: BookQuote, author: str | None) -> bool:
    text = f"💬 <b>Kun iqtibosi</b>\n\n<i>«{_e(quote.text)}»</i>"
    if author:
        text += f"\n\n— {_e(author)}"
    return await queue(session, kind=ChannelPostKind.QUOTE, text=text, dedup_key=f"quote:{quote.id}")


async def report_posted(session: AsyncSession, report: Any) -> bool:
    """An event report was approved: the channel shows how it went, with the report's photos."""
    from app.models import ReportPhoto

    event = await session.get(Event, report.event_id) if report.event_id else None
    if event is None:
        return False
    book = await _book(session, event.book_id)
    local = event.starts_at.astimezone(local_tz())
    day = f"{local.day}-{MONTHS_UZ[local.month - 1]} {local.year}-yil"
    if book is not None:
        head = f"📚 <b>{day} kuni «{_e(book.title)}» ({_e(book.author)}) asari bo'yicha davra suhbati bo'lib o'tdi.</b>"
    else:
        head = f"📚 <b>{day} kuni «{_e(event.title)}» tadbiri bo'lib o'tdi.</b>"
    lines = [
        head,
        "",
        "Talabalar faol ishtirok etib, munosib rag'batlantirildilar. Fikr almashgan, savol bergan va "
        "kitob olamiga birga sayohat qilgan barcha kitobxonlarga rahmat! 🙏",
    ]
    chat = normalize_chat_id(str(await get_setting(session, "channel.chat_id")))
    if isinstance(chat, str):
        lines += ["", f'📣 <a href="https://t.me/{chat[1:]}">{_e(chat)}</a> — kuzatib boring!']
    photos = list(
        await session.scalars(
            select(ReportPhoto.object_key)
            .where(ReportPhoto.report_id == report.id)
            .order_by(ReportPhoto.sort_order, ReportPhoto.created_at)
            .limit(10)
        )
    )
    more = str(await get_setting(session, "channel.more_photos_url") or "")
    return await queue(
        session,
        kind=ChannelPostKind.REPORT,
        text="\n".join(lines),
        dedup_key=f"report:{event.id}",
        photo_key=photos[0] if photos else book.cover_key if book else None,
        photo_url=None if photos or (book and book.cover_key) else (book.cover_url if book else None),
        extra_photos=photos[1:],
        buttons=[{"text": "📸 Boshqa rasmlar", "url": more}] if more else [],
    )


# ---------------------------------------------------------------------------- scheduled posts

REMINDERS = (
    ("day", timedelta(hours=24)),
    ("today", timedelta(hours=3)),
)


def _event_reminder_text(event: Event, book: Book | None, which: str, shifts: list[Any] | None = None) -> str:
    from app.services import event_times

    local = event.starts_at.astimezone(local_tz())
    when = "Ertaga" if which == "day" else "Bugun"
    if shifts:
        head = f"⏰ <b>{when} «{_e(event.title)}»!</b>\n" + "\n".join(
            f"🕒 {_e(event_times.shift_text(shift))}" for shift in shifts
        )
    else:
        head = _pick(
            (
                f"⏰ <b>{when} soat {local:%H:%M} da «{_e(event.title)}»!</b>",
                f"🔔 <b>Eslatma: {when.lower()} soat {local:%H:%M} da uchrashamiz!</b>\n«{_e(event.title)}»",
            ),
            f"{event.id}:{which}",
        )
    lines = [head]
    if event.location:
        lines.append(f"📍 {_e(event.location)}")
    if book is not None:
        lines += [
            "",
            _pick(
                (
                    f"📚 «{_e(book.title)}» asarini o'qib kelamiz — tayyormisiz?",
                    f"📖 «{_e(book.title)}» ni o'qib bo'ldingizmi? Fikrlaringizni olib keling!",
                    f"📚 Mavzu: «{_e(book.title)}» — {_e(book.author)}. Oxirgi sahifalarga ulguring!",
                ),
                f"{event.id}:{which}:book",
            ),
        ]
    lines += ["", "Kelganlar davomatni QR orqali belgilaydi va ball oladi ✅"]
    return "\n".join(lines)


async def _event_reminders(session: AsyncSession, now: datetime) -> int:
    events = list(
        await session.scalars(
            select(Event).where(
                Event.deleted_at.is_(None),
                Event.status == EventStatus.PUBLISHED,
                Event.starts_at > now,
                Event.starts_at <= now + timedelta(hours=25),
            )
        )
    )
    from app.services.events import shifts_of

    queued = 0
    for event in events:
        book = await _book(session, event.book_id)
        shifts = await shifts_of(session, event.id)
        for which, before in REMINDERS:
            due = event.starts_at - before
            if not (due <= now < due + timedelta(hours=2)):
                continue
            # The day-before reminder at night would become a morning post on the day itself.
            if (
                which == "day"
                and next_daytime(now).astimezone(local_tz()).date() == event.starts_at.astimezone(local_tz()).date()
            ):
                continue
            queued += await queue(
                session,
                kind=ChannelPostKind.EVENT_REMINDER,
                text=_event_reminder_text(event, book, which, shifts),
                dedup_key=f"event_reminder:{event.id}:{which}",
                buttons=[event_button(event)],
            )
    return queued


NUDGES_END = (
    "📖 <b>Asarni tugatay deb qoldingizmi, kitobxonlar?</b>\n\n«{title}» — {author}\n"
    "⏳ Muddat: {deadline} gacha ({days} kun qoldi).\nOxirgi sahifalarga oz qoldi — marra sizniki! 💪",
    "⏳ <b>{days} kun qoldi!</b>\n\n«{title}» — {author}\n"
    "Kuniga 30–40 bet — va kitob tugaydi. Tugatganlar botda belgilab, ball oladi 🏅",
    "☕ <b>Bugun kitobga 20 daqiqa ajrating</b>\n\n«{title}» sizni kutyapti. Muddat: {deadline}.\n"
    "Kim allaqachon tugatdi? Botda belgilang ✅",
    "🏁 <b>Marra yaqin!</b>\n\n«{title}» — {author}\n{days} kun qoldi ({deadline} gacha).\n"
    "Tugatganlar uchun test va ball tayyor 🎯",
    "📚 <b>Oxirgi boblar — eng qiziqlari!</b>\n\n«{title}» — {author}\nMuddat: {deadline} ({days} kun).\n"
    "Bugun bir bob — ertaga yana bittasi 💪",
    "🔔 <b>Eslatma: «{title}»</b>\n\n{days} kundan so'ng ({deadline}) muhokama vaqti. Kitobni tugatib "
    "qo'ying — botda «O'qib tugatdim» deb belgilang ✅",
)
NUDGES_MIDDLE = (
    "📚 <b>Yarmiga yetdingizmi?</b>\n\n«{title}» — {author}\n"
    "O'qish muddatining yarmi o'tdi. Qaysi qahramon sizga ko'proq yoqyapti? 🤔",
    "🔖 <b>Kitobxonlar, qayerga yetdik?</b>\n\n«{title}» ni o'qish davom etmoqda. Muddat: {deadline}.\n"
    "Hali boshlamagan bo'lsangiz ham kech emas! 📖",
    "☕ <b>Yo'lning yarmi!</b>\n\n«{title}» — {author}\nMuddat: {deadline}. Eng yoqqan jumlangizni "
    "«Iqtiboslar sandig'i»ga saqlang 💬",
    "📖 <b>«{title}» qanday ketyapti?</b>\n\nMuddat: {deadline}. Mutolaa kundaligiga betlarni yozib "
    "boring — seriyangiz o'ssin 🔥",
    "🤔 <b>Savol: «{title}»da sizni nima hayratga soldi?</b>\n\n{author} asarini o'qish davom etmoqda "
    "({deadline} gacha). Fikrlaringizni tadbirda aytasiz!",
)


_editable(
    "channel.nudges_end",
    "Kitob muddati tugashiga 1–3 kun qolganda",
    NUDGES_END,
    "{title} — kitob, {author} — muallif, {deadline} — muddat, {days} — qolgan kunlar",
)
_editable(
    "channel.nudges_middle",
    "Kitob o'qish muddatining yarmida",
    NUDGES_MIDDLE,
    "{title} — kitob, {author} — muallif, {deadline} — muddat, {days} — qolgan kunlar",
)


async def _reading_nudges(session: AsyncSession, now: datetime) -> int:
    today = now.astimezone(local_tz()).date()
    books = list(
        await session.scalars(
            select(Book).where(
                Book.deleted_at.is_(None),
                Book.status == BookStatus.ACTIVE,
                Book.deadline.is_not(None),
                Book.deadline >= today,
            )
        )
    )
    queued = 0
    for book in books:
        assert book.deadline is not None
        days_left = (book.deadline - today).days
        values = {
            "title": _e(book.title),
            "author": _e(book.author),
            "deadline": format_human_date(book.deadline),
            "days": days_left,
        }
        if 1 <= days_left <= 3:
            text = _pick(phrases("channel.nudges_end"), f"nudge:{book.id}:end").format(**values)
            queued += await queue(
                session, kind=ChannelPostKind.READING_NUDGE, text=text, dedup_key=f"nudge:{book.id}:end"
            )
            continue
        start = book.start_date or (book.created_at.astimezone(local_tz()).date() if book.created_at else None)
        if start is not None and (book.deadline - start).days >= 10:
            middle = start + (book.deadline - start) / 2
            if today >= middle and days_left > 3:
                text = _pick(phrases("channel.nudges_middle"), f"nudge:{book.id}:middle").format(**values)
                queued += await queue(
                    session, kind=ChannelPostKind.READING_NUDGE, text=text, dedup_key=f"nudge:{book.id}:middle"
                )
    return queued


INVITES = (
    "📚 <b>Kitobxonlar klubiga qo'shiling!</b>\n\nBotimizda:\n✅ tadbirlarda QR davomat\n"
    "📝 kitoblar bo'yicha testlar\n🏆 reyting va 🎓 sertifikatlar\n🎁 sovg'alar va promokodlar\n\n"
    "Klubda allaqachon {members} kitobxon bor. Siz ham qo'shiling 👇",
    "✨ <b>Kitob o'qish — endi yanada qiziqarli!</b>\n\nO'qing, testda qatnashing, ball to'plang va oyning "
    "eng faol kitobxoni bo'ling. G'oliblarga sertifikat va sovg'alar 🎁\n\n"
    "{members} nafar talaba allaqachon biz bilan. Navbat sizda 👇",
    "🪪 <b>O'z Kitobxon pasportingizni oling!</b>\n\nBotda ro'yxatdan o'ting — rasmli a'zolik kartasi, "
    "natijalaringiz va yutuqlaringiz bir joyda.\nTadbirlar, testlar, reyting va sovg'alar sizni kutmoqda 👇",
    "📖 <b>Kitob o'qiysizmi? Unda siz bizniki!</b>\n\nJavoningiz, mutolaa kundaligingiz, iqtiboslar "
    "sandig'ingiz va shaxsiy missiyalaringiz — barchasi bitta botda.\n{members} kitobxon allaqachon shu yerda 👇",
    "🏆 <b>Bu hafta kim yetakchi bo'ladi?</b>\n\nTadbirlarga keling, testlarni yeching, kitoblarni o'qib "
    "tugating — har biri ball. Eng faollar sertifikat va sovg'a oladi 🎁\n{members} nafar a'zo kutmoqda 👇",
    "💬 <b>Fikringiz bilan bo'lishing!</b>\n\nKlub a'zolari iqtibos va taassurotlarini yozadi, eng "
    "yaxshilari chiroyli kartochka bo'lib kanalda chiqadi. {members} kitobxon bilan birga bo'ling 👇",
)


_editable("channel.invites", "Haftalik taklif posti (dushanba)", INVITES, "{members} — a'zolar soni")


def _pick_week(options: tuple[str, ...], week: int) -> str:
    return options[week % len(options)]


async def _weekly_invite(session: AsyncSession, now: datetime) -> int:
    local = now.astimezone(local_tz())
    if local.weekday() != 0 or local.time() < time(10, 0):
        return 0
    year, week, _ = local.isocalendar()
    members = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
        )
        or 0
    )
    key = f"invite:{year}-W{week:02d}"
    return int(
        await queue(
            session,
            kind=ChannelPostKind.INVITE,
            text=_pick_week(phrases("channel.invites"), week).format(members=members),
            dedup_key=key,
        )
    )


async def _monthly_leaders(session: AsyncSession, now: datetime) -> int:
    from app.services.ranking import ranking

    local = now.astimezone(local_tz())
    if local.day > 7 or (local.day == 1 and local.time() < time(10, 0)):
        return 0
    this_month = datetime.combine(local.date().replace(day=1), time.min, tzinfo=local_tz())
    last_month = (this_month - timedelta(days=1)).replace(day=1)
    period = f"{last_month:%Y-%m}"
    if period < MONTHLY_SINCE:
        return 0
    if await session.scalar(select(ChannelPost.id).where(ChannelPost.dedup_key == f"monthly:{period}")):
        return 0
    board = await ranking(session, period="month", scope="all", viewer=None, limit=3, between=(last_month, this_month))
    if not board.items:
        return 0
    month = MONTHS_UZ[last_month.month - 1]
    lines = [f"🏆 <b>{month.capitalize()} oyining eng faol kitobxonlari</b>", ""]
    for row in board.items:
        lines.append(f"{MEDALS.get(row.rank, '🏅')} {_e(row.name)} — {row.total} ball")
    lines += ["", "Tabriklaymiz! 🎉 Yangi oyda reyting noldan boshlanadi — birinchi bo'lish imkoniyati hammada bor 💪"]
    return int(await queue(session, kind=ChannelPostKind.RESULTS, text="\n".join(lines), dedup_key=f"monthly:{period}"))


async def scheduled_posts(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: reminders, reading nudges, the weekly invitation and the month's leaders."""
    if not await is_on(session):
        return 0
    now = now or datetime.now(UTC)
    return (
        await _event_reminders(session, now)
        + await _reading_nudges(session, now)
        + await _weekly_invite(session, now)
        + await _monthly_leaders(session, now)
    )


# ---------------------------------------------------------------------------- admins look first

EDIT_HOLD = timedelta(minutes=30)  # how long a post waits for the admin's new text


async def review_minutes(session: AsyncSession) -> int:
    return int(await get_setting(session, "channel.review_minutes") or 0)


def plain_text(text: str) -> str:
    """The post without HTML tags (an admin preview of a cut text, the panel's edit field)."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


async def request_reviews(session: AsyncSession, now: datetime | None = None) -> int:
    """Show automatic posts to the admins a few minutes before they go out: post now, cancel or edit.
    Nobody answers — the post goes out at its time. Returns how many posts were shown."""
    from app.security.permissions import Perm
    from app.services.notifications import enqueue_for_members
    from app.services.rbac import admins_with_permission

    minutes = await review_minutes(session)
    if minutes <= 0:
        return 0
    now = now or datetime.now(UTC)
    posts = list(
        await session.scalars(
            select(ChannelPost)
            .where(
                ChannelPost.status == ChannelPostStatus.PENDING,
                ChannelPost.kind != ChannelPostKind.MANUAL,
                ChannelPost.review_sent_at.is_(None),
                ChannelPost.reviewed_at.is_(None),
                ChannelPost.scheduled_at > now,
                ChannelPost.scheduled_at <= now + timedelta(minutes=minutes),
            )
            .order_by(ChannelPost.scheduled_at)
            .with_for_update(skip_locked=True)
        )
    )
    chat = normalize_chat_id(str(await get_setting(session, "channel.chat_id")))
    for post in posts:
        post.review_sent_at = now
        local = post.scheduled_at.astimezone(local_tz())
        body = post.text if len(post.text) <= 3000 else _e(plain_text(post.text)[:3000]) + "…"
        text = (
            f"👀 <b>Kanal uchun post tayyor</b> — soat {local:%H:%M} da {_e(chat)} kanaliga o'zi chiqadi.\n"
            "Hech kim javob bermasa, shunday joylanadi.\n\n"
            f"{body}" + ("\n\n🖼 <i>Rasm bilan</i>" if post.photo_key or post.photo_url else "")
        )
        await enqueue_for_members(
            session,
            type_=NotificationType.SYSTEM,
            text=text,
            dedup_prefix=f"channel-review:{post.id}",
            members=admins_with_permission(Perm.NOTIFICATION_SEND),
            sync=f"channel-review:{post.id}",
            payload={
                "base": text,
                "buttons": [
                    {
                        "row": [
                            {"text": "✅ Hozir joylash", "callback": f"chp:ok:{post.id.hex}"},
                            {"text": "❌ Bekor qilish", "callback": f"chp:no:{post.id.hex}"},
                        ]
                    },
                    {"text": "✏️ Matnni o'zgartirish", "callback": f"chp:edit:{post.id.hex}"},
                ],
            },
            priority=1,
        )
    if posts:
        await session.commit()
        wake_sender()
    return len(posts)


async def _pending(
    session: AsyncSession, post_id: uuid.UUID, *, actor_id: uuid.UUID | None = None, by_preview: bool = False
) -> ChannelPost:
    """A post not sent yet. ``by_preview``: an admin pressed a button under the preview, so a post
    another admin already decided on is left alone (the panel can still change it)."""
    post = await session.get(ChannelPost, post_id, with_for_update=True, populate_existing=True)
    if post is None:
        raise NotFoundError("POST_NOT_FOUND", "Post topilmadi.")
    if post.status != ChannelPostStatus.PENDING:
        raise ConflictError(
            "POST_NOT_PENDING",
            "Bu post allaqachon joylangan." if post.status == ChannelPostStatus.SENT else "Bu post bekor qilingan.",
        )
    if by_preview and post.reviewed_at is not None and post.reviewed_by != actor_id:
        raise ConflictError("POST_REVIEWED", "Boshqa admin bu postni allaqachon ko'rib chiqdi.")
    return post


def _reviewed(post: ChannelPost, actor_id: uuid.UUID, now: datetime) -> None:
    post.reviewed_at = now
    post.reviewed_by = actor_id


async def _settle_review(session: AsyncSession, post: ChannelPost, actor_id: uuid.UUID, what: str) -> None:
    """Every admin's preview of this post shows what happened to it (and who did it)."""
    from app.services import copies

    status = f"{what} — {await copies.admin_name(session, actor_id)}, {copies.stamp()}"
    await copies.settle(session, f"channel-review:{post.id}", status, buttons=[])


async def publish_now(
    session: AsyncSession, *, actor_id: uuid.UUID, post_id: uuid.UUID, by_preview: bool = False
) -> ChannelPost:
    """An admin pressed «hoziroq jo'natish»: it goes out right now, even at night — the admin chose
    this consciously, so the club's quiet hours are not applied to a manual publish."""
    post = await _pending(session, post_id, actor_id=actor_id, by_preview=by_preview)
    now = datetime.now(UTC)
    _reviewed(post, actor_id, now)
    post.scheduled_at = now
    record_audit(
        session, actor_id=actor_id, action="CHANNEL_POST_APPROVE", entity_type="channel_post", entity_id=post.id
    )
    await _settle_review(session, post, actor_id, "✅ <b>Kanalga joylashga yuborildi</b>")
    await session.commit()
    wake_sender()
    return post


async def hold_for_edit(session: AsyncSession, *, actor_id: uuid.UUID, post_id: uuid.UUID) -> ChannelPost:
    """The admin is writing a new text: the post waits up to 30 minutes, then goes out as it is."""
    post = await _pending(session, post_id, actor_id=actor_id, by_preview=True)
    now = datetime.now(UTC)
    _reviewed(post, actor_id, now)
    post.scheduled_at = max(post.scheduled_at, now + EDIT_HOLD)
    await _settle_review(session, post, actor_id, "✏️ <b>Matni o'zgartirilmoqda</b>")
    await session.commit()
    return post


async def edit_post(session: AsyncSession, *, actor_id: uuid.UUID, post_id: uuid.UUID, text: str) -> ChannelPost:
    """New text (Telegram HTML) for a post not sent yet; it goes out right away."""
    body = text.strip()
    if not body:
        raise BadRequestError("EMPTY_POST", "Post matnini yozing.")
    if len(body) > 4000:
        raise BadRequestError("POST_TOO_LONG", "Post 4000 belgidan oshmasin.")
    post = await _pending(session, post_id)
    now = datetime.now(UTC)
    before = post.text
    post.text = body
    _reviewed(post, actor_id, now)
    post.scheduled_at = next_daytime(now)
    record_audit(
        session,
        actor_id=actor_id,
        action="CHANNEL_POST_EDIT",
        entity_type="channel_post",
        entity_id=post.id,
        before={"text": before[:500]},
        after={"text": body[:500]},
    )
    await _settle_review(session, post, actor_id, "✏️ <b>Matn o'zgartirildi va joylashga yuborildi</b>")
    await session.commit()
    wake_sender()
    return post


# ---------------------------------------------------------------------------- admin


async def manual_post(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    text: str,
    photo: bytes | None = None,
    sticker_id: uuid.UUID | None = None,
    with_button: bool = True,
    scheduled_at: datetime | None = None,
    target_chat_id: str | None = None,
) -> ChannelPost:
    from app.services.storage import get_storage

    # Which channel this goes to. NULL means the primary club channel; an extra channel is stored as-is.
    primary = await _primary_chat(session)
    target: str | None = None
    if target_chat_id:
        chosen = normalize_chat_id(target_chat_id)
        allowed = {dest["chat_id"] for dest in await destinations(session)}
        if chosen is None or str(chosen) not in allowed:
            raise BadRequestError(
                "UNKNOWN_CHANNEL", "Bu kanal ro'yxatda yo'q. Sozlamalar → 📣 Telegram kanal bo'limida qo'shing."
            )
        if primary is None or str(chosen) != str(primary):
            target = str(chosen)
    elif primary is None:
        raise ConflictError("CHANNEL_NOT_SET", "Sozlamalarda kanal manzilini kiriting (masalan, @FJSTIMutolaaxona).")
    body = text.strip()
    if not body and photo is None:
        raise BadRequestError("EMPTY_POST", "Post matnini yozing yoki rasm tanlang.")
    sticker = None
    if sticker_id is not None:
        sticker = await session.get(ChannelSticker, sticker_id)
        if sticker is None:
            raise NotFoundError("STICKER_NOT_FOUND", "Stiker topilmadi.")
    photo_key = None
    if photo is not None:
        image = prepare_image(photo)
        photo_key = f"channel/{uuid.uuid4()}.jpg"
        await get_storage().put(photo_key, image, "image/jpeg")
    post = ChannelPost(
        kind=ChannelPostKind.MANUAL,
        text=html.escape(body, quote=False),
        photo_key=photo_key,
        sticker_file_id=sticker.file_id if sticker else None,
        buttons=[JOIN_BUTTON] if with_button else [],
        scheduled_at=scheduled_at or datetime.now(UTC),
        target_chat_id=target,
        created_by=actor_id,
    )
    session.add(post)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="CHANNEL_POST",
        entity_type="channel_post",
        entity_id=post.id,
        after={"text": body[:500], "photo": photo_key is not None, "scheduled_at": post.scheduled_at.isoformat()},
    )
    await session.commit()
    wake_sender()
    return post


async def test_post(session: AsyncSession, *, actor_id: uuid.UUID) -> ChannelPost:
    club = await get_setting(session, "org.club_name")
    return await manual_post(
        session,
        actor_id=actor_id,
        text=f"✅ {club} boti kanalga ulandi! Endi bu yerda tadbirlar, yangi kitoblar va g'oliblar e'lon qilinadi.",
    )


async def cancel_post(
    session: AsyncSession, *, actor_id: uuid.UUID, post_id: uuid.UUID, by_preview: bool = False
) -> ChannelPost:
    post = await _pending(session, post_id, actor_id=actor_id, by_preview=by_preview)
    post.status = ChannelPostStatus.CANCELLED
    _reviewed(post, actor_id, datetime.now(UTC))
    record_audit(
        session, actor_id=actor_id, action="CHANNEL_POST_CANCEL", entity_type="channel_post", entity_id=post.id
    )
    await _settle_review(session, post, actor_id, "❌ <b>Bekor qilindi</b>")
    await session.commit()
    return post


async def recent_posts(session: AsyncSession, limit: int = 50) -> list[ChannelPost]:
    return list(
        await session.scalars(
            select(ChannelPost).order_by(ChannelPost.scheduled_at.desc(), ChannelPost.created_at.desc()).limit(limit)
        )
    )


async def stickers(session: AsyncSession) -> list[ChannelSticker]:
    return list(await session.scalars(select(ChannelSticker).order_by(ChannelSticker.created_at)))


async def add_sticker(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    file_id: str,
    file_unique_id: str,
    emoji: str | None,
    set_name: str | None,
    is_animated: bool,
) -> tuple[ChannelSticker | None, int]:
    """Returns (the new sticker or None if it was saved before, how many are saved now)."""
    created = await session.scalar(
        insert(ChannelSticker)
        .values(
            file_id=file_id,
            file_unique_id=file_unique_id,
            emoji=emoji,
            set_name=set_name,
            is_animated=is_animated,
            mood=mood_for(emoji),
            created_by=actor_id,
        )
        .on_conflict_do_nothing(index_elements=[ChannelSticker.file_unique_id])
        .returning(ChannelSticker)
    )
    await session.commit()
    total = int(await session.scalar(select(func.count()).select_from(ChannelSticker)) or 0)
    return created, total


async def delete_sticker(session: AsyncSession, *, actor_id: uuid.UUID, sticker_id: uuid.UUID) -> None:
    sticker = await session.get(ChannelSticker, sticker_id)
    if sticker is None:
        raise NotFoundError("STICKER_NOT_FOUND", "Stiker topilmadi.")
    await session.delete(sticker)
    record_audit(session, actor_id=actor_id, action="CHANNEL_STICKER_DELETE", entity_type="channel_sticker")
    await session.commit()


async def status(session: AsyncSession) -> dict[str, Any]:
    chat = normalize_chat_id(str(await get_setting(session, "channel.chat_id")))
    last_sent = await session.scalar(select(func.max(ChannelPost.sent_at)))
    last_failed = await session.scalar(
        select(ChannelPost)
        .where(ChannelPost.status == ChannelPostStatus.FAILED)
        .order_by(ChannelPost.created_at.desc())
        .limit(1)
    )
    pending = int(
        await session.scalar(
            select(func.count()).select_from(ChannelPost).where(ChannelPost.status == ChannelPostStatus.PENDING)
        )
        or 0
    )
    return {
        "enabled": bool(await get_setting(session, "channel.enabled")),
        "chat_id": str(chat) if chat is not None else None,
        "link": f"https://t.me/{chat[1:]}" if isinstance(chat, str) else None,
        "pending": pending,
        "last_sent_at": last_sent,
        "last_error": last_failed.last_error
        if last_failed and (not last_sent or last_failed.created_at > last_sent)
        else None,
        "targets": await destinations(session),
    }
