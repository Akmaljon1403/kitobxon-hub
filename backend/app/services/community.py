"""«💬 A'zolar fikrlari»: quotes, thoughts, impressions and testimonials members send to the club.

The member writes any time (the Mini App, or /fikr in the bot), and is asked after finishing a book or
rating an event. What they write:

* goes to the common pool — the feed every member reads (after an admin approves it, unless the club
  publishes at once) — and quotes and thoughts are also kept in the member's own quote box;
* can be used by the club as it wishes: a card (six designs) in the channel, a message with the card to
  all or part of the members, the quote of the day, or sent to the admin's own chat to forward anywhere.

Points are given once per accepted text (``community.points``, a monthly cap), and once more when the
club features it or posts it in the channel (``community.featured_points``).
"""

from __future__ import annotations

import html
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    AttendanceRecord,
    Book,
    BookQuote,
    Contribution,
    ContributionLike,
    Event,
    Faculty,
    SavedQuote,
    User,
)
from app.models.enums import (
    AttendanceStatus,
    ContributionKind,
    ContributionStatus,
    NotificationType,
    QuoteStatus,
    ScoreCategory,
    UserStatus,
)
from app.services import share_cards
from app.services.audit import record_audit
from app.services.notifications import app_button, celebrate, enqueue_notification
from app.services.scoring import award_points
from app.services.settings import get_setting
from app.utils.timezone import local_tz

MIN_TEXT = 8
MAX_TEXT = 1000
MAX_SOURCE = 255

# kind → (what the member picks, the label on the card, a short word)
KINDS: dict[ContributionKind, tuple[str, str, str]] = {
    ContributionKind.QUOTE: ("📖 Kitobdan iqtibos", "Kitobxonlar iqtiboslari", "iqtibos"),
    ContributionKind.THOUGHT: ("💡 O'z fikrim", "Kitobxon fikri", "fikr"),
    ContributionKind.BOOK: ("📚 Kitob haqida taassurot", "Kitob haqida taassurot", "taassurot"),
    ContributionKind.EVENT: ("📅 Tadbir haqida taassurot", "Tadbir taassuroti", "taassurot"),
    ContributionKind.CLUB: ("🌟 Klub haqida e'tirof", "Klub haqida e'tirof", "e'tirof"),
}
BOX_KINDS = (ContributionKind.QUOTE, ContributionKind.THOUGHT)  # also kept in the member's quote box
USES = {
    "channel": "📣 Kanalda",
    "members": "📢 A'zolarga yuborilgan",
    "quote_of_day": "📜 Kun iqtibosi",
    "me": "📨 Adminga yuborilgan",
}


def quoted(text: str) -> str:
    """«…» around the words, unless they already begin with a quote mark."""
    return text if text.lstrip()[:1] in ("«", '"', "\u201c", "\u201e", "'") else f"«{text}»"


def kind_title(kind: ContributionKind) -> str:
    return KINDS[kind][0]


def _clean(value: str | None, limit: int) -> str | None:
    text = " ".join((value or "").replace("\r", "").split(" ")).strip()
    return text[:limit] if text else None


def _today_start() -> datetime:
    return datetime.combine(datetime.now(local_tz()).date(), time.min, local_tz())


def _month_start() -> datetime:
    today = datetime.now(local_tz()).date()
    return datetime.combine(today.replace(day=1), time.min, local_tz())


def author_name(user: User | None, show_name: bool = True) -> str:
    """How the author is shown to everybody: «Madina K.» (or «Klub a'zosi» if they asked)."""
    if user is None or not show_name:
        return "Klub a'zosi"
    return share_cards.display(user)


def author_line(user: User | None, faculty: str | None, show_name: bool = True) -> str:
    name = author_name(user, show_name)
    return f"{name}, {faculty}" if faculty and show_name else name


# ---------------------------------------------------------------------------- members: writing


async def submit(
    session: AsyncSession,
    user: User,
    *,
    kind: ContributionKind,
    text: str,
    source: str | None = None,
    book_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
    show_name: bool = True,
    style: str | None = None,
    save_to_box: bool = True,
    saved_quote_id: uuid.UUID | None = None,
) -> Contribution:
    clean = _clean(text, MAX_TEXT + 1)
    if not clean or len(clean) < MIN_TEXT:
        raise BadRequestError("TEXT_TOO_SHORT", f"Kamida {MIN_TEXT} ta belgi yozing.")
    if len(clean) > MAX_TEXT:
        raise BadRequestError("TEXT_TOO_LONG", f"Ko'pi bilan {MAX_TEXT} ta belgi.")
    limit = int(await get_setting(session, "community.daily_limit"))
    today = await session.scalar(
        select(func.count())
        .select_from(Contribution)
        .where(Contribution.user_id == user.id, Contribution.created_at >= _today_start())
    )
    if (today or 0) >= limit:
        raise ConflictError("DAILY_LIMIT", f"Bugun {limit} ta fikr yubordingiz — ertaga yana yozing. Rahmat!")
    same = await session.scalar(
        select(Contribution.id).where(Contribution.user_id == user.id, func.lower(Contribution.text) == clean.lower())
    )
    if same is not None:
        raise ConflictError("ALREADY_SENT", "Bu matnni avval yuborgansiz.")

    source = _clean(source, MAX_SOURCE)
    if book_id is not None:
        book = await session.get(Book, book_id)
        if book is None or book.deleted_at is not None:
            raise NotFoundError("BOOK_NOT_FOUND", "Kitob topilmadi.")
        source = source or " — ".join(part for part in (book.author, f"«{book.title}»") if part)
    if event_id is not None:
        event = await session.get(Event, event_id)
        if event is None or event.deleted_at is not None:
            raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
        attended = await session.scalar(
            select(AttendanceRecord.id).where(
                AttendanceRecord.event_id == event_id,
                AttendanceRecord.user_id == user.id,
                AttendanceRecord.status.in_((AttendanceStatus.VERIFIED, AttendanceStatus.SUSPICIOUS)),
            )
        )
        if attended is None:
            raise ConflictError("NOT_ATTENDED", "Faqat o'zingiz qatnashgan tadbir haqida yozish mumkin.")
        source = source or f"«{event.title}» tadbiri"
    if kind == ContributionKind.EVENT and event_id is None:
        raise BadRequestError("EVENT_REQUIRED", "Qaysi tadbir haqida yozayotganingizni tanlang.")

    if save_to_box and kind in BOX_KINDS and saved_quote_id is None:
        from app.services import reading_journal

        kept = await reading_journal.save_quote(
            session, user, text=clean, source=source or ("O'z fikrim" if kind == ContributionKind.THOUGHT else None)
        )
        saved_quote_id = kept.id
    elif saved_quote_id is not None:
        owned = await session.scalar(
            select(SavedQuote.id).where(SavedQuote.id == saved_quote_id, SavedQuote.user_id == user.id)
        )
        if owned is None:
            raise NotFoundError("QUOTE_NOT_FOUND", "Iqtibos topilmadi.")

    auto = bool(await get_setting(session, "community.auto_publish"))
    item = Contribution(
        user_id=user.id,
        kind=kind,
        text=clean,
        source=source,
        book_id=book_id,
        event_id=event_id,
        saved_quote_id=saved_quote_id,
        show_name=show_name,
        style=share_cards.style_of(style).code,
        status=ContributionStatus.APPROVED if auto else ContributionStatus.PENDING,
        uses=[],
    )
    session.add(item)
    await session.flush()
    if auto:
        await _accepted(session, item, user)
    else:
        await _tell_moderators(session, item, user)
    await session.commit()
    await session.refresh(item)
    return item


async def share_from_box(
    session: AsyncSession, user: User, saved_quote_id: uuid.UUID, *, show_name: bool = True, style: str | None = None
) -> Contribution:
    """A quote already in the member's own box goes to the common pool too."""
    quote = await session.scalar(
        select(SavedQuote).where(SavedQuote.id == saved_quote_id, SavedQuote.user_id == user.id)
    )
    if quote is None:
        raise NotFoundError("QUOTE_NOT_FOUND", "Iqtibos topilmadi.")
    if quote.book_quote_id is not None:
        raise ConflictError("CLUB_QUOTE", "Bu iqtibos klubning o'zidan — u allaqachon hammaga ma'lum.")
    known = await session.scalar(select(Contribution).where(Contribution.saved_quote_id == quote.id))
    if known is not None:
        return known
    return await submit(
        session,
        user,
        kind=ContributionKind.QUOTE if quote.source and quote.source != "O'z fikrim" else ContributionKind.THOUGHT,
        text=quote.text,
        source=None if quote.source == "O'z fikrim" else quote.source,
        show_name=show_name,
        style=style,
        save_to_box=False,
        saved_quote_id=quote.id,
    )


async def box_states(session: AsyncSession, quote_ids: list[uuid.UUID]) -> dict[uuid.UUID, Contribution]:
    """For «💬 Iqtiboslar sandig'i»: which saved quotes are in the common pool (and how they are doing)."""
    if not quote_ids:
        return {}
    rows = await session.scalars(select(Contribution).where(Contribution.saved_quote_id.in_(quote_ids)))
    return {row.saved_quote_id: row for row in rows if row.saved_quote_id is not None}


async def set_box_visibility(
    session: AsyncSession, user: User, saved_quote_id: uuid.UUID, visibility: str, *, show_name: bool = True
) -> Contribution | None:
    """«🌍 Umumiy» puts a saved quote into the common pool (as the admins' rules say — straight away or after
    a look); «🔒 Shaxsiy» takes it back. The quote itself always stays in the member's box."""
    from app.services import features
    from app.services.settings import get_setting

    if visibility == "COMMON":
        if not await get_setting(session, "community.quote_box_common"):
            raise ConflictError("COMMON_OFF", "Iqtiboslarni umumiy qilish hozircha yopiq.")
        if await features.allowed(session, user, "community") != "on":
            raise ConflictError("COMMUNITY_OFF", "«A'zolar fikrlari» bo'limi hozircha yopiq.")
        return await share_from_box(session, user, saved_quote_id, show_name=show_name)
    quote = await session.scalar(
        select(SavedQuote).where(SavedQuote.id == saved_quote_id, SavedQuote.user_id == user.id)
    )
    if quote is None:
        raise NotFoundError("QUOTE_NOT_FOUND", "Iqtibos topilmadi.")
    await session.execute(
        delete(Contribution).where(Contribution.saved_quote_id == quote.id, Contribution.user_id == user.id)
    )
    await session.commit()
    return None


async def delete_own(session: AsyncSession, user: User, contribution_id: uuid.UUID) -> None:
    """The author takes it back (their quote box keeps the quote)."""
    result = await session.execute(
        delete(Contribution).where(Contribution.id == contribution_id, Contribution.user_id == user.id)
    )
    if not result.rowcount:
        raise NotFoundError("CONTRIBUTION_NOT_FOUND", "Topilmadi.")
    await session.commit()


async def like(session: AsyncSession, user: User, contribution_id: uuid.UUID) -> tuple[bool, int]:
    """❤️ on or off. Returns (liked now, likes)."""
    item = await session.get(Contribution, contribution_id, with_for_update=True)
    if item is None or item.status != ContributionStatus.APPROVED:
        raise NotFoundError("CONTRIBUTION_NOT_FOUND", "Topilmadi.")
    removed = await session.execute(
        delete(ContributionLike).where(ContributionLike.contribution_id == item.id, ContributionLike.user_id == user.id)
    )
    if removed.rowcount:
        item.likes = max(0, item.likes - 1)
        liked = False
    else:
        session.add(ContributionLike(contribution_id=item.id, user_id=user.id))
        item.likes += 1
        liked = True
    await session.commit()
    return liked, item.likes


# ---------------------------------------------------------------------------- members: reading


def _with_author() -> Select[Any]:
    return (
        select(Contribution, User, Faculty.name)
        .join(User, User.id == Contribution.user_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
    )


def describe(item: Contribution, user: User | None, faculty: str | None, *, liked: bool = False) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "kind_title": kind_title(item.kind),
        "text": item.text,
        "source": item.source,
        "author": author_line(user, faculty, item.show_name),
        "show_name": item.show_name,
        "style": item.style,
        "status": item.status,
        "featured": item.featured,
        "likes": item.likes,
        "liked": liked,
        "book_id": item.book_id,
        "event_id": item.event_id,
        "in_channel": any(use.get("where") == "channel" for use in item.uses or []),
        "created_at": item.created_at,
    }


async def _liked(session: AsyncSession, viewer: User, ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    rows = await session.scalars(
        select(ContributionLike.contribution_id).where(
            ContributionLike.user_id == viewer.id, ContributionLike.contribution_id.in_(ids)
        )
    )
    return set(rows)


async def feed(
    session: AsyncSession,
    viewer: User,
    *,
    kind: ContributionKind | None = None,
    sort: str = "new",
    limit: int = 30,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """The common feed: approved texts, featured first on the «new» tab, or the most liked."""
    query = _with_author().where(Contribution.status == ContributionStatus.APPROVED)
    if kind is not None:
        query = query.where(Contribution.kind == kind)
    if sort == "top":
        query = query.order_by(Contribution.likes.desc(), Contribution.created_at.desc())
    else:
        query = query.order_by(Contribution.featured.desc(), Contribution.created_at.desc())
    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    liked = await _liked(session, viewer, [item.id for item, _, _ in rows])
    return [describe(item, user, faculty, liked=item.id in liked) for item, user, faculty in rows]


async def mine(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            _with_author().where(Contribution.user_id == user.id).order_by(Contribution.created_at.desc()).limit(200)
        )
    ).all()
    return [describe(item, author, faculty) for item, author, faculty in rows]


async def visible(
    session: AsyncSession, viewer: User, contribution_id: uuid.UUID
) -> tuple[Contribution, User, str | None]:
    """An approved text, or the viewer's own one in any state."""
    row = (await session.execute(_with_author().where(Contribution.id == contribution_id))).first()
    if row is None or (row[0].status != ContributionStatus.APPROVED and row[0].user_id != viewer.id):
        raise NotFoundError("CONTRIBUTION_NOT_FOUND", "Topilmadi.")
    return row[0], row[1], row[2]


async def book_options(session: AsyncSession, user: User) -> dict[str, Any]:
    """What the member can write about: club books and the events they came to (the latest first)."""
    from app.models.enums import BookStatus

    books = (
        await session.execute(
            select(Book.id, Book.title, Book.author)
            .where(Book.deleted_at.is_(None), Book.status != BookStatus.DRAFT)
            .order_by(Book.created_at.desc())
            .limit(50)
        )
    ).all()
    events = (
        await session.execute(
            select(Event.id, Event.title, Event.starts_at)
            .join(AttendanceRecord, AttendanceRecord.event_id == Event.id)
            .where(
                AttendanceRecord.user_id == user.id,
                AttendanceRecord.status.in_((AttendanceStatus.VERIFIED, AttendanceStatus.SUSPICIOUS)),
                Event.deleted_at.is_(None),
            )
            .order_by(Event.starts_at.desc())
            .limit(30)
        )
    ).all()
    return {
        "kinds": [{"code": kind, "title": title} for kind, (title, _, _) in KINDS.items()],
        "styles": [{"code": style.code, "title": style.title} for style in share_cards.STYLES.values()],
        "books": [{"id": row.id, "title": row.title, "author": row.author} for row in books],
        "events": [{"id": row.id, "title": row.title, "starts_at": row.starts_at} for row in events],
    }


# ---------------------------------------------------------------------------- the card


async def card_png(
    session: AsyncSession, item: Contribution, user: User | None, faculty: str | None, style: str | None = None
) -> bytes:
    import asyncio

    from app.bot.setup import resolve_bot_username

    footer = share_cards.footer_text(await resolve_bot_username())
    return await asyncio.to_thread(
        share_cards.styled_card,
        item.text,
        label=KINDS[item.kind][1],
        source=item.source,
        by=author_line(user, faculty, item.show_name),
        footer=footer,
        style=style or item.style,
    )


def card_filename(item: Contribution) -> str:
    return f"kitobxon-{KINDS[item.kind][2].replace(chr(39), '')}-{item.id.hex[:8]}.png"


# ---------------------------------------------------------------------------- after an approval


async def _points(session: AsyncSession, item: Contribution, key: str, setting: str, *, capped: bool) -> int:
    value = int(await get_setting(session, setting))
    if value <= 0:
        return 0
    if capped:
        limit = int(await get_setting(session, "community.monthly_points_limit"))
        if limit:
            given = await session.scalar(
                select(func.count())
                .select_from(Contribution)
                .where(
                    Contribution.user_id == item.user_id,
                    Contribution.points_awarded.is_(True),
                    Contribution.reviewed_at >= _month_start(),
                )
            )
            if (given or 0) >= limit:
                return 0
    awarded = await award_points(
        session,
        user_id=item.user_id,
        amount=value,
        category=ScoreCategory.CAMPAIGN,
        idempotency_key=key,
        source_type="contribution",
        source_id=item.id,
        reason=f"A'zolar fikrlari: {KINDS[item.kind][2]}",
    )
    return value if awarded else 0


async def _accepted(session: AsyncSession, item: Contribution, author: User | None = None) -> None:
    """In the feed now: points once, and the author is told."""
    item.reviewed_at = item.reviewed_at or datetime.now(UTC)
    points = 0
    if not item.points_awarded:
        points = await _points(session, item, f"contribution:{item.id}", "community.points", capped=True)
        item.points_awarded = True
    extra = f" (+{points} ball)" if points else ""
    await enqueue_notification(
        session,
        user_id=item.user_id,
        type_=NotificationType.SYSTEM,
        text=(
            f"🌟 Rahmat! {KINDS[item.kind][2].capitalize()}ingiz «💬 A'zolar fikrlari» lentasiga qo'shildi{extra}. "
            "Boshqa kitobxonlar uni o'qiydi va ❤️ bosadi."
        ),
        dedup_key=f"contribution-accepted:{item.id}",
        payload=app_button("community", "💬 Lentani ochish"),
    )


async def _celebrated(session: AsyncSession, item: Contribution, why: str) -> None:
    """Featured or posted in the channel: extra points once and a congratulation."""
    points = await _points(session, item, f"contribution-star:{item.id}", "community.featured_points", capped=False)
    extra = f" Sizga +{points} ball!" if points else ""
    await enqueue_notification(
        session,
        user_id=item.user_id,
        type_=NotificationType.SYSTEM,
        text=f"🎉 {why}{extra} Yozishda davom eting — sizning so'zlaringiz boshqalarni ilhomlantiradi.",
        dedup_key=f"contribution-star:{item.id}",
        payload=celebrate(app_button("community", "💬 A'zolar fikrlari")),
    )


async def _tell_moderators(session: AsyncSession, item: Contribution, author: User) -> None:
    if not await get_setting(session, "community.notify_admins"):
        return
    from app.security.permissions import Perm
    from app.services.notifications import enqueue_for_members
    from app.services.rbac import admins_with_permission

    source = f"\n<i>{html.escape(item.source)}</i>" if item.source else ""
    text = (
        f"💬 <b>Yangi {KINDS[item.kind][2]}</b> — {html.escape(author.last_name)} {html.escape(author.first_name)}\n\n"
        f"{html.escape(quoted(item.text[:700]))}{source}"
    )
    await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=text,
        dedup_prefix=f"contribution-new:{item.id}",
        members=admins_with_permission(Perm.COMMUNITY_MANAGE),
        sync=f"contribution:{item.id}",
        payload={
            "base": text,
            "buttons": [
                {
                    "row": [
                        {"text": "✅ Lentaga", "callback": f"cm:ok:{item.id.hex}"},
                        {"text": "⭐ Tanlash", "callback": f"cm:star:{item.id.hex}"},
                        {"text": "🙈 Yashirish", "callback": f"cm:hide:{item.id.hex}"},
                    ]
                },
                {"text": "🛠 Hammasi panelda", "admin_route": "community"},
            ],
        },
    )


# ---------------------------------------------------------------------------- the Admin Panel


async def get(session: AsyncSession, contribution_id: uuid.UUID) -> Contribution:
    item = await session.get(Contribution, contribution_id)
    if item is None:
        raise NotFoundError("CONTRIBUTION_NOT_FOUND", "Topilmadi.")
    return item


async def admin_counts(session: AsyncSession) -> dict[str, int]:
    rows = dict((await session.execute(select(Contribution.status, func.count()).group_by(Contribution.status))).all())
    featured = await session.scalar(
        select(func.count()).select_from(Contribution).where(Contribution.featured.is_(True))
    )
    return {
        "PENDING": int(rows.get(ContributionStatus.PENDING, 0)),
        "APPROVED": int(rows.get(ContributionStatus.APPROVED, 0)),
        "HIDDEN": int(rows.get(ContributionStatus.HIDDEN, 0)),
        "FEATURED": int(featured or 0),
    }


async def admin_list(
    session: AsyncSession,
    *,
    status: str | None = None,
    kind: ContributionKind | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    origin: str | None = None,
) -> list[dict[str, Any]]:
    query = _with_author()
    if origin == "BOX":  # made common from members' quote boxes
        query = query.where(Contribution.saved_quote_id.is_not(None))
    if status == "FEATURED":
        query = query.where(Contribution.featured.is_(True))
    elif status:
        query = query.where(Contribution.status == ContributionStatus(status))
    if kind is not None:
        query = query.where(Contribution.kind == kind)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                Contribution.text.ilike(pattern),
                Contribution.source.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            )
        )
    rows = (await session.execute(query.order_by(Contribution.created_at.desc()).limit(limit).offset(offset))).all()
    result = []
    for item, user, faculty in rows:
        row = describe(item, user, faculty)
        row.update(
            {
                "member": f"{user.last_name} {user.first_name}",
                "member_details": " · ".join(
                    part for part in (faculty, f"{user.course}-kurs" if user.course else None, user.group_name) if part
                ),
                "uses": [{**use, "title": USES.get(use.get("where", ""), use.get("where"))} for use in item.uses or []],
                "reviewed_at": item.reviewed_at,
            }
        )
        result.append(row)
    return result


async def moderate(
    session: AsyncSession, *, actor_id: uuid.UUID, contribution_id: uuid.UUID, action: str
) -> Contribution:
    """approve | hide | feature | unfeature | pending."""
    item = await session.get(Contribution, contribution_id, with_for_update=True)
    if item is None:
        raise NotFoundError("CONTRIBUTION_NOT_FOUND", "Topilmadi.")
    before = {"status": item.status, "featured": item.featured}
    now = datetime.now(UTC)
    if action == "approve":
        if item.status != ContributionStatus.APPROVED:
            item.status = ContributionStatus.APPROVED
            item.reviewed_by, item.reviewed_at = actor_id, now
            await _accepted(session, item)
    elif action == "hide":
        item.status = ContributionStatus.HIDDEN
        item.featured = False
        item.reviewed_by, item.reviewed_at = actor_id, now
    elif action == "pending":
        item.status = ContributionStatus.PENDING
        item.featured = False
    elif action == "feature":
        if item.status != ContributionStatus.APPROVED:
            item.status = ContributionStatus.APPROVED
            item.reviewed_by, item.reviewed_at = actor_id, now
            await _accepted(session, item)
        if not item.featured:
            item.featured = True
            await _celebrated(
                session, item, f"{KINDS[item.kind][2].capitalize()}ingiz «⭐ Tanlanganlar» qatoriga kirdi!"
            )
    elif action == "unfeature":
        item.featured = False
    else:
        raise BadRequestError("UNKNOWN_ACTION", "Noma'lum amal.")
    record_audit(
        session,
        actor_id=actor_id,
        action=f"CONTRIBUTION_{action.upper()}",
        entity_type="contribution",
        entity_id=item.id,
        before={key: str(value) for key, value in before.items()},
        after={"status": str(item.status), "featured": item.featured},
    )
    from app.services import copies

    # every moderator's copy in the bot shows the decision (whoever took it, in the bot or the panel)
    await copies.settle(
        session,
        f"contribution:{item.id}",
        f"{DECIDED[action]} — {await copies.admin_name(session, actor_id)}, {copies.stamp()}",
        buttons=[{"text": "🛠 Hammasi panelda", "admin_route": "community"}],
    )
    await session.commit()
    await session.refresh(item)
    return item


DECIDED = {
    "approve": "✅ <b>Lentaga chiqarildi</b>",
    "feature": "⭐ <b>Tanlanganlarga qo'shildi</b>",
    "hide": "🙈 <b>Yashirildi</b>",
    "pending": "⏳ <b>Qayta ko'rib chiqishga qaytarildi</b>",
    "unfeature": "☆ <b>Tanlanganlardan olindi</b>",
}


async def edit(
    session: AsyncSession, *, actor_id: uuid.UUID, contribution_id: uuid.UUID, text: str, source: str | None
) -> Contribution:
    """Fix a typo before the club uses it (written to the audit log)."""
    item = await get(session, contribution_id)
    clean = _clean(text, MAX_TEXT)
    if not clean or len(clean) < MIN_TEXT:
        raise BadRequestError("TEXT_TOO_SHORT", f"Kamida {MIN_TEXT} ta belgi.")
    before = {"text": item.text, "source": item.source}
    item.text, item.source = clean, _clean(source, MAX_SOURCE)
    record_audit(
        session,
        actor_id=actor_id,
        action="CONTRIBUTION_EDIT",
        entity_type="contribution",
        entity_id=item.id,
        before=before,
        after={"text": item.text, "source": item.source},
    )
    await session.commit()
    await session.refresh(item)
    return item


async def author_of(session: AsyncSession, item: Contribution) -> tuple[User | None, str | None]:
    row = (
        await session.execute(
            select(User, Faculty.name).outerjoin(Faculty, Faculty.id == User.faculty_id).where(User.id == item.user_id)
        )
    ).first()
    return (row[0], row[1]) if row else (None, None)


async def _used(session: AsyncSession, item: Contribution, where: str, actor_id: uuid.UUID, **extra: Any) -> None:
    actor = await session.get(User, actor_id)
    item.uses = [
        *(item.uses or []),
        {
            "where": where,
            "at": datetime.now(UTC).isoformat(),
            "by": f"{actor.first_name} {actor.last_name}" if actor else "—",
            **extra,
        },
    ]


def default_caption(item: Contribution) -> str:
    return {
        ContributionKind.QUOTE: "💬 Kitobxonlarimiz saqlagan iqtiboslardan.",
        ContributionKind.THOUGHT: "💡 Kitobxonlarimiz fikrlaridan.",
        ContributionKind.BOOK: "📚 Kitobxonlarimiz taassurotlaridan.",
        ContributionKind.EVENT: "📅 Tadbirimiz haqida kitobxonlarimiz fikri.",
        ContributionKind.CLUB: "🌟 Kitobxonlarimiz klub haqida.",
    }[item.kind] + "\n\nSiz ham yozing: botda /fikr yoki ilovada «💬 A'zolar fikrlari»."


async def _approve_for_use(session: AsyncSession, item: Contribution, actor_id: uuid.UUID) -> None:
    if item.status != ContributionStatus.APPROVED:
        item.status = ContributionStatus.APPROVED
        item.reviewed_by, item.reviewed_at = actor_id, datetime.now(UTC)
        await _accepted(session, item)


async def to_channel(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    contribution_id: uuid.UUID,
    style: str | None = None,
    caption: str | None = None,
    scheduled_at: datetime | None = None,
) -> dict[str, Any]:
    """The card in the club channel (with the caption under it), now or at a set time."""
    from app.services import channel

    item = await get(session, contribution_id)
    user, faculty = await author_of(session, item)
    image = await card_png(session, item, user, faculty, style)
    await _approve_for_use(session, item, actor_id)
    await _used(session, item, "channel", actor_id, style=share_cards.style_of(style or item.style).code)
    if not any(use.get("where") == "channel" for use in (item.uses or [])[:-1]):
        await _celebrated(session, item, f"{KINDS[item.kind][2].capitalize()}ingiz klub kanalida e'lon qilinadi!")
    await session.flush()
    post = await channel.manual_post(
        session,
        actor_id=actor_id,
        text=(caption if caption is not None else default_caption(item)).strip(),
        photo=image,
        scheduled_at=scheduled_at,
    )
    return {"post_id": post.id, "scheduled_at": post.scheduled_at}


async def to_members(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    contribution_id: uuid.UUID,
    style: str | None = None,
    caption: str | None = None,
    faculty_id: uuid.UUID | None = None,
    course: int | None = None,
    group_name: str | None = None,
    dry_run: bool = False,
) -> int:
    """The card as a message to all (or part of the) active members."""
    from app.services.members import normalize_group
    from app.services.notifications import enqueue_for_members
    from app.services.storage import get_storage

    conditions: list[Any] = [User.status == UserStatus.ACTIVE, User.deleted_at.is_(None)]
    if faculty_id is not None:
        conditions.append(User.faculty_id == faculty_id)
    if course is not None:
        conditions.append(User.course == course)
    if group_name:
        conditions.append(User.group_name == normalize_group(group_name))
    members = select(User.id).where(*conditions)
    if dry_run:
        return int(await session.scalar(select(func.count()).select_from(members.subquery())) or 0)
    item = await get(session, contribution_id)
    user, faculty = await author_of(session, item)
    look = share_cards.style_of(style or item.style).code
    image = await card_png(session, item, user, faculty, look)
    key = f"community/{item.id.hex}-{look}-{uuid.uuid4().hex[:6]}.png"
    await get_storage().put(key, image, "image/png")
    await _approve_for_use(session, item, actor_id)
    send_id = uuid.uuid4()
    count = await enqueue_for_members(
        session,
        type_=NotificationType.ADMIN_MESSAGE,
        text=html.escape((caption if caption is not None else default_caption(item)).strip(), quote=False),
        dedup_prefix=f"contribution-send:{send_id}",
        members=members,
        payload={"photo_key": key, **app_button("community", "💬 A'zolar fikrlari")},
        priority=4,
    )
    await _used(session, item, "members", actor_id, count=count)
    record_audit(
        session,
        actor_id=actor_id,
        action="CONTRIBUTION_TO_MEMBERS",
        entity_type="contribution",
        entity_id=item.id,
        after={
            "recipients": count,
            "faculty_id": str(faculty_id) if faculty_id else None,
            "course": course,
            "group_name": group_name,
        },
    )
    await session.commit()
    from app.services.notifications import wake_sender

    wake_sender()
    return count


async def to_me(session: AsyncSession, *, actor: User, contribution_id: uuid.UUID, style: str | None = None) -> None:
    """The card in the admin's own chat with the bot: from there it can be forwarded anywhere."""
    from aiogram.types import BufferedInputFile

    from app.services import delivery

    item = await get(session, contribution_id)
    user, faculty = await author_of(session, item)
    image = await card_png(session, item, user, faculty, style)
    caption = quoted(item.text[:800]) + (f"\n— {item.source}" if item.source else "")
    caption += f"\n\n✍️ {author_line(user, faculty, item.show_name)}"
    bot = delivery.runtime_bot()
    await delivery.explain_failures(
        bot.send_photo(
            actor.telegram_id,
            BufferedInputFile(image, filename=card_filename(item)),
            caption=html.escape(caption[:1000], quote=False),
        )
    )
    await _used(session, item, "me", actor.id)
    await session.commit()


async def next_free_quote_day(session: AsyncSession, after: date | None = None) -> date:
    """The first day from tomorrow without a scheduled quote of the day."""
    day = after or datetime.now(local_tz()).date() + timedelta(days=1)
    taken = set(
        await session.scalars(
            select(BookQuote.scheduled_date).where(
                BookQuote.scheduled_date >= day,
                BookQuote.deleted_at.is_(None),
                BookQuote.status != QuoteStatus.ARCHIVED,
            )
        )
    )
    while day in taken:
        day += timedelta(days=1)
    return day


async def to_quote_of_day(
    session: AsyncSession, *, actor_id: uuid.UUID, contribution_id: uuid.UUID, day: date | None = None
) -> BookQuote:
    """The text becomes a club quote, scheduled as the quote of the day (sent to members and the channel)."""
    item = await get(session, contribution_id)
    user, _ = await author_of(session, item)
    if day is not None and day <= datetime.now(local_tz()).date():
        raise BadRequestError("DAY_IN_PAST", "Ertangi yoki keyingi kunni tanlang.")
    day = day or await next_free_quote_day(session)
    busy = await session.scalar(
        select(BookQuote.id).where(
            BookQuote.scheduled_date == day, BookQuote.deleted_at.is_(None), BookQuote.status != QuoteStatus.ARCHIVED
        )
    )
    if busy is not None:
        raise ConflictError("DAY_TAKEN", "Bu kunga boshqa iqtibos rejalashtirilgan — boshqa kunni tanlang.")
    writer = item.source.split(" — ")[0] if item.source and item.kind == ContributionKind.QUOTE else None
    quote = BookQuote(
        book_id=item.book_id,
        text=item.text,
        author=writer or (author_name(user, item.show_name) if item.kind != ContributionKind.QUOTE else None),
        source=item.source,
        scheduled_date=day,
        status=QuoteStatus.SCHEDULED,
        created_by=actor_id,
    )
    session.add(quote)
    await _approve_for_use(session, item, actor_id)
    await _used(session, item, "quote_of_day", actor_id, day=day.isoformat())
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="CONTRIBUTION_QUOTE_OF_DAY",
        entity_type="contribution",
        entity_id=item.id,
        after={"quote_id": str(quote.id), "day": day.isoformat()},
    )
    await session.commit()
    await session.refresh(quote)
    return quote


# ---------------------------------------------------------------------------- asking at the right moment


async def ask_after_book(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    book_id: uuid.UUID | None,
    key: str,
    shelf_item_id: uuid.UUID | None = None,
) -> None:
    """A book is finished: rate it and answer the three questions (the reading diary), and — if the member
    wishes — share an impression with the club. The member is no longer asked for a standalone book quote."""
    from app.services import features

    if not await get_setting(session, "community.ask_after_book"):
        return
    buttons: list[dict[str, Any]] = []
    if shelf_item_id is not None:
        buttons.append({"text": "⭐ Baholash va 3 savol", "app_route": f"shelf/{shelf_item_id}"})
    community_on = await features.allowed(session, user, "community") == "on"
    if community_on:
        route = "community/new?kind=BOOK" + (f"&book={book_id}" if book_id else "")
        buttons.append({"text": "✍️ Klubga taassurot", "app_route": route})
    if not buttons:
        return
    share_line = " Istasangiz, bir-ikki jumla taassurotingizni klub bilan ham ulashing." if community_on else ""
    await enqueue_notification(
        session,
        user_id=user.id,
        type_=NotificationType.SYSTEM,
        text=(
            f"📖 «{html.escape(title)}» — o'qib tugatdingiz, barakalla!\n\n"
            "Kitobni baholang va uchta qisqa savolga javob bering — bu sizning mutolaa kundaligingizda qoladi."
            + share_line
        ),
        dedup_key=f"ask-book:{user.id}:{key}",
        payload={"buttons": buttons},
    )


def event_invite_button(event_id: uuid.UUID) -> dict[str, Any]:
    return {"text": "✍️ Taassurot yozish", "app_route": f"community/new?kind=EVENT&event={event_id}"}


async def pending_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Contribution).where(Contribution.status == ContributionStatus.PENDING)
        )
        or 0
    )
