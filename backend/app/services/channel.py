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
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Book, BookQuote, ChannelPost, ChannelSticker, Event, Test, User
from app.models.enums import (
    BookStatus,
    ChannelPostKind,
    ChannelPostStatus,
    EventStatus,
    UserStatus,
)
from app.services.audit import record_audit
from app.services.notifications import wake_sender
from app.services.settings import get_setting
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


async def _random_sticker(session: AsyncSession) -> str | None:
    if not await get_setting(session, "channel.stickers"):
        return None
    ids = list(await session.scalars(select(ChannelSticker.file_id)))
    return random.choice(ids) if ids else None  # noqa: S311 - decoration, not security


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
) -> bool:
    """Queue a post. Automatic posts respect the switches, the night hours and get a sticker.
    Returns False when nothing was queued (switched off or already posted)."""
    if automatic and not await is_on(session, kind):
        return False
    when = scheduled_at or datetime.now(UTC)
    if automatic:
        when = next_daytime(when)
        sticker_file_id = sticker_file_id or await _random_sticker(session)
    statement = (
        insert(ChannelPost)
        .values(
            kind=kind,
            text=text.strip(),
            dedup_key=dedup_key,
            photo_key=photo_key,
            photo_url=photo_url,
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


async def event_announced(session: AsyncSession, event: Event) -> bool:
    if event.status != EventStatus.PUBLISHED or event.starts_at <= datetime.now(UTC):
        return False
    book = await _book(session, event.book_id)
    local = event.starts_at.astimezone(local_tz())
    lines = [
        _pick(
            ("📅 <b>Yangi tadbir!</b>", "🎉 <b>Kitobxonlar, yangi uchrashuv!</b>", "📣 <b>Diqqat, kitobxonlar!</b>"),
            f"event:{event.id}",
        ),
        "",
        f"<b>«{_e(event.title)}»</b>",
        f"🗓 {_weekday_date(event.starts_at)}, soat {local:%H:%M}",
    ]
    if event.location:
        lines.append(f"📍 {_e(event.location)}")
    if book is not None:
        lines += ["", f"📚 <b>«{_e(book.title)}»</b> — {_e(book.author)} asarini o'qib kelamiz!"]
    if event.description:
        lines += ["", _e(event.description.strip()[:600])]
    lines += [
        "",
        "✅ Davomat QR kod orqali, faol qatnashchilarga ball, sertifikat va sovg'alar.",
        "👇 Ro'yxatdan o'tish va eslatma olish uchun botga qo'shiling.",
    ]
    return await queue(
        session,
        kind=ChannelPostKind.EVENT,
        text="\n".join(lines),
        dedup_key=f"event:{event.id}",
        photo_key=book.cover_key if book is not None else None,
        photo_url=book.cover_url if book is not None and not book.cover_key else None,
    )


async def book_announced(session: AsyncSession, book: Book) -> bool:
    if book.status != BookStatus.ACTIVE or book.deleted_at is not None:
        return False
    lines = [
        _pick(
            (
                "📚 <b>Yangi kitob — birga o'qiymiz!</b>",
                "📖 <b>Navbatdagi asarimiz</b>",
                "✨ <b>Yangi kitob e'lon qilindi</b>",
            ),
            f"book:{book.id}",
        ),
        "",
        f"<b>«{_e(book.title)}»</b> — {_e(book.author)}",
    ]
    if book.pages:
        lines.append(f"📄 {book.pages} bet")
    if book.deadline:
        lines.append(f"🗓 O'qish muddati: {format_human_date(book.deadline)} gacha")
    if book.description:
        lines += ["", _e(book.description.strip()[:500])]
    lines += [
        "",
        "O'qib tugatganlarga ball, testda g'oliblarga sertifikat 🏆",
        "👇 Kitobni botda «o'qiyapman» deb belgilang",
    ]
    return await queue(
        session,
        kind=ChannelPostKind.BOOK,
        text="\n".join(lines),
        dedup_key=f"book:{book.id}",
        photo_key=book.cover_key,
        photo_url=book.cover_url if not book.cover_key else None,
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


# ---------------------------------------------------------------------------- scheduled posts

REMINDERS = (
    ("day", timedelta(hours=24)),
    ("today", timedelta(hours=3)),
)


def _event_reminder_text(event: Event, book: Book | None, which: str) -> str:
    local = event.starts_at.astimezone(local_tz())
    when = "Ertaga" if which == "day" else "Bugun"
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
    queued = 0
    for event in events:
        book = await _book(session, event.book_id)
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
                text=_event_reminder_text(event, book, which),
                dedup_key=f"event_reminder:{event.id}:{which}",
            )
    return queued


NUDGES_END = (
    "📖 <b>Asarni tugatay deb qoldingizmi, kitobxonlar?</b>\n\n«{title}» — {author}\n"
    "⏳ Muddat: {deadline} gacha ({days} kun qoldi).\nOxirgi sahifalarga oz qoldi — marra sizniki! 💪",
    "⏳ <b>{days} kun qoldi!</b>\n\n«{title}» — {author}\n"
    "Kuniga 30–40 bet — va kitob tugaydi. Tugatganlar botda belgilab, ball oladi 🏅",
    "☕ <b>Bugun kitobga 20 daqiqa ajrating</b>\n\n«{title}» sizni kutyapti. Muddat: {deadline}.\n"
    "Kim allaqachon tugatdi? Botda belgilang ✅",
)
NUDGES_MIDDLE = (
    "📚 <b>Yarmiga yetdingizmi?</b>\n\n«{title}» — {author}\n"
    "O'qish muddatining yarmi o'tdi. Qaysi qahramon sizga ko'proq yoqyapti? 🤔",
    "🔖 <b>Kitobxonlar, qayerga yetdik?</b>\n\n«{title}» ni o'qish davom etmoqda. Muddat: {deadline}.\n"
    "Hali boshlamagan bo'lsangiz ham kech emas! 📖",
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
            text = _pick(NUDGES_END, f"nudge:{book.id}:end").format(**values)
            queued += await queue(
                session, kind=ChannelPostKind.READING_NUDGE, text=text, dedup_key=f"nudge:{book.id}:end"
            )
            continue
        start = book.start_date or (book.created_at.astimezone(local_tz()).date() if book.created_at else None)
        if start is not None and (book.deadline - start).days >= 10:
            middle = start + (book.deadline - start) / 2
            if today >= middle and days_left > 3:
                text = _pick(NUDGES_MIDDLE, f"nudge:{book.id}:middle").format(**values)
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
)


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
            text=INVITES[week % len(INVITES)].format(members=members),
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
) -> ChannelPost:
    from app.services.storage import get_storage

    if normalize_chat_id(str(await get_setting(session, "channel.chat_id"))) is None:
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


async def cancel_post(session: AsyncSession, *, actor_id: uuid.UUID, post_id: uuid.UUID) -> ChannelPost:
    post = await session.get(ChannelPost, post_id)
    if post is None:
        raise NotFoundError("POST_NOT_FOUND", "Post topilmadi.")
    if post.status != ChannelPostStatus.PENDING:
        raise ConflictError("POST_NOT_PENDING", "Faqat hali yuborilmagan postni bekor qilish mumkin.")
    post.status = ChannelPostStatus.CANCELLED
    record_audit(
        session, actor_id=actor_id, action="CHANNEL_POST_CANCEL", entity_type="channel_post", entity_id=post.id
    )
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
    }
