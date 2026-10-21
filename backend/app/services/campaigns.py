"""Reading contests («1 hafta — 1 kitob», «1 oy — 1 kitob» …).

Several contests can run at the same time, each with its own book(s). Everything is keyed by the
campaign id — participants, the channel announcement (``dedup_key="campaign:<id>"``), the report —
so two contests never mix, even on the same book. A member joins a contest, marks its book read, an
admin confirms it, and the contest's points go to the member once.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Book, Campaign, CampaignBook, CampaignParticipant, User
from app.models.enums import CampaignStatus, NotificationType, ScoreCategory
from app.services.audit import record_audit
from app.services.settings import get_setting, update_setting
from app.utils.timezone import format_date

ACTIVE_STATUSES = (CampaignStatus.ACTIVE,)
EDITABLE_STATUSES = (CampaignStatus.DRAFT, CampaignStatus.ACTIVE)


async def point_defaults(session: AsyncSession) -> tuple[int, int]:
    """The last-used contest points, pre-filled into the «new contest» form inside Tadbirlar."""
    return (
        int(await get_setting(session, "campaign.default_points_per_book")),
        int(await get_setting(session, "campaign.default_completion_bonus")),
    )


async def remember_defaults(
    session: AsyncSession, *, actor_id: uuid.UUID, points_per_book: int, completion_bonus: int
) -> None:
    """Keep the points the admin just used, so the next contest starts from the same values."""
    await update_setting(session, key="campaign.default_points_per_book", value=points_per_book, actor_id=actor_id)
    await update_setting(session, key="campaign.default_completion_bonus", value=completion_bonus, actor_id=actor_id)


@dataclass(frozen=True)
class ParticipantState:
    joined: bool
    completed: bool
    verified: bool


# ---------------------------------------------------------------------------- reading


async def get(session: AsyncSession, campaign_id: uuid.UUID) -> Campaign:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None or campaign.deleted_at is not None:
        raise NotFoundError("CAMPAIGN_NOT_FOUND", "Tanlov topilmadi.")
    return campaign


async def for_event(session: AsyncSession, event_id: uuid.UUID) -> Campaign | None:
    """The one reading contest tied to an event (if any)."""
    return await session.scalar(select(Campaign).where(Campaign.event_id == event_id, Campaign.deleted_at.is_(None)))


async def by_events(session: AsyncSession, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, Campaign]:
    """{event_id: its contest} for a batch of events (the admin event list)."""
    if not event_ids:
        return {}
    rows = await session.scalars(
        select(Campaign).where(Campaign.event_id.in_(event_ids), Campaign.deleted_at.is_(None))
    )
    return {campaign.event_id: campaign for campaign in rows if campaign.event_id is not None}


async def book_ids_by_campaigns(
    session: AsyncSession, campaign_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """{campaign_id: [book_id, …] in order} for a batch of contests."""
    result: dict[uuid.UUID, list[uuid.UUID]] = {campaign_id: [] for campaign_id in campaign_ids}
    if campaign_ids:
        rows = await session.execute(
            select(CampaignBook.campaign_id, CampaignBook.book_id)
            .where(CampaignBook.campaign_id.in_(campaign_ids))
            .order_by(CampaignBook.sort_order)
        )
        for campaign_id, book_id in rows:
            result[campaign_id].append(book_id)
    return result


async def sync_event_campaign(
    session: AsyncSession, *, actor_id: uuid.UUID, event: Any, spec: dict[str, Any] | None
) -> None:
    """Create, update or unlink the one reading contest attached to an event — inside the caller's
    transaction (does NOT commit). ``spec`` None unlinks the contest (it is kept, just freed from the
    event); a dict upserts it. The contest's dates always follow the event's own window."""
    existing = await for_event(session, event.id)
    if spec is None:
        if existing is not None:
            existing.event_id = None
        return
    book_ids = [uuid.UUID(str(value)) for value in spec["book_ids"]]
    if not book_ids:
        raise BadRequestError("CAMPAIGN_NO_BOOK", "Tanlov uchun kamida bitta kitob tanlang.")
    _check_dates(event.starts_at, event.ends_at)
    if existing is None:
        campaign = Campaign(
            name=str(spec["name"]).strip(),
            description=(spec.get("description") or None),
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            points_per_book=int(spec["points_per_book"]),
            completion_bonus=int(spec["completion_bonus"]),
            status=CampaignStatus.DRAFT,
            created_by=actor_id,
            event_id=event.id,
        )
        session.add(campaign)
        await session.flush()
        await _set_books(session, campaign.id, book_ids)
        record_audit(
            session,
            actor_id=actor_id,
            action="CAMPAIGN_CREATE",
            entity_type="campaign",
            entity_id=campaign.id,
            after={"name": campaign.name, "event_id": str(event.id)},
        )
    else:
        if existing.status not in EDITABLE_STATUSES:
            return  # a finished contest is immutable; editing the event leaves it untouched
        existing.name = str(spec["name"]).strip()
        existing.description = spec.get("description") or None
        existing.starts_at = event.starts_at
        existing.ends_at = event.ends_at
        existing.points_per_book = int(spec["points_per_book"])
        existing.completion_bonus = int(spec["completion_bonus"])
        await _set_books(session, existing.id, book_ids)
        record_audit(
            session, actor_id=actor_id, action="CAMPAIGN_UPDATE", entity_type="campaign", entity_id=existing.id
        )


async def books_of(session: AsyncSession, campaign_id: uuid.UUID) -> list[Book]:
    return list(
        await session.scalars(
            select(Book)
            .join(CampaignBook, CampaignBook.book_id == Book.id)
            .where(CampaignBook.campaign_id == campaign_id)
            .order_by(CampaignBook.sort_order, Book.title)
        )
    )


async def _counts(session: AsyncSession, campaign_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    """{campaign_id: (participants, verified completions)} — each counted within its own contest."""
    if not campaign_ids:
        return {}
    rows = await session.execute(
        select(
            CampaignParticipant.campaign_id,
            func.count(),
            func.count(CampaignParticipant.verified_at),
        )
        .where(CampaignParticipant.campaign_id.in_(campaign_ids))
        .group_by(CampaignParticipant.campaign_id)
    )
    return {campaign_id: (int(total), int(verified)) for campaign_id, total, verified in rows}


async def list_campaigns(session: AsyncSession) -> list[tuple[Campaign, list[Book], tuple[int, int]]]:
    campaigns = list(
        await session.scalars(select(Campaign).where(Campaign.deleted_at.is_(None)).order_by(Campaign.starts_at.desc()))
    )
    counts = await _counts(session, [campaign.id for campaign in campaigns])
    return [(campaign, await books_of(session, campaign.id), counts.get(campaign.id, (0, 0))) for campaign in campaigns]


async def participants(session: AsyncSession, campaign_id: uuid.UUID) -> list[tuple[CampaignParticipant, User]]:
    rows = await session.execute(
        select(CampaignParticipant, User)
        .join(User, User.id == CampaignParticipant.user_id)
        .where(CampaignParticipant.campaign_id == campaign_id)
        .order_by(CampaignParticipant.verified_at.is_(None), User.last_name, User.first_name)
    )
    return [(row[0], row[1]) for row in rows.all()]


# ---------------------------------------------------------------------------- admin CRUD


async def _set_books(session: AsyncSession, campaign_id: uuid.UUID, book_ids: list[uuid.UUID]) -> None:
    await session.execute(delete(CampaignBook).where(CampaignBook.campaign_id == campaign_id))
    seen: set[uuid.UUID] = set()
    order = 0
    for book_id in book_ids:
        if book_id in seen:
            continue
        book = await session.get(Book, book_id)
        if book is None or book.deleted_at is not None:
            raise BadRequestError("BOOK_NOT_FOUND", "Tanlangan kitob topilmadi.")
        session.add(CampaignBook(campaign_id=campaign_id, book_id=book_id, sort_order=order))
        seen.add(book_id)
        order += 1
    if not seen:
        raise BadRequestError("CAMPAIGN_NO_BOOK", "Kamida bitta kitob tanlang.")


def _check_dates(starts_at: datetime, ends_at: datetime) -> None:
    if ends_at <= starts_at:
        raise BadRequestError("CAMPAIGN_DATES", "Tugash vaqti boshlanishdan keyin bo'lsin.")


async def create(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    name: str,
    description: str | None,
    starts_at: datetime,
    ends_at: datetime,
    points_per_book: int,
    completion_bonus: int,
    book_ids: list[uuid.UUID],
    event_id: uuid.UUID | None = None,
) -> Campaign:
    _check_dates(starts_at, ends_at)
    campaign = Campaign(
        name=name.strip(),
        description=(description or None),
        starts_at=starts_at,
        ends_at=ends_at,
        points_per_book=points_per_book,
        completion_bonus=completion_bonus,
        status=CampaignStatus.DRAFT,
        created_by=actor_id,
        event_id=event_id,
    )
    session.add(campaign)
    await session.flush()
    await _set_books(session, campaign.id, book_ids)
    record_audit(
        session,
        actor_id=actor_id,
        action="CAMPAIGN_CREATE",
        entity_type="campaign",
        entity_id=campaign.id,
        after={"name": campaign.name},
    )
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def update(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    campaign: Campaign,
    name: str,
    description: str | None,
    starts_at: datetime,
    ends_at: datetime,
    points_per_book: int,
    completion_bonus: int,
    book_ids: list[uuid.UUID],
) -> Campaign:
    if campaign.status not in EDITABLE_STATUSES:
        raise ConflictError("CAMPAIGN_LOCKED", "Yakunlangan tanlovni tahrirlab bo'lmaydi.")
    _check_dates(starts_at, ends_at)
    campaign.name = name.strip()
    campaign.description = description or None
    campaign.starts_at = starts_at
    campaign.ends_at = ends_at
    campaign.points_per_book = points_per_book
    campaign.completion_bonus = completion_bonus
    await _set_books(session, campaign.id, book_ids)
    record_audit(session, actor_id=actor_id, action="CAMPAIGN_UPDATE", entity_type="campaign", entity_id=campaign.id)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def delete_campaign(session: AsyncSession, *, actor_id: uuid.UUID, campaign: Campaign) -> None:
    campaign.deleted_at = datetime.now(UTC)
    record_audit(session, actor_id=actor_id, action="CAMPAIGN_DELETE", entity_type="campaign", entity_id=campaign.id)
    await session.commit()


async def set_status(
    session: AsyncSession, *, actor_id: uuid.UUID, campaign: Campaign, status: CampaignStatus, announce: bool = False
) -> Campaign:
    if status == CampaignStatus.ACTIVE and not await books_of(session, campaign.id):
        raise ConflictError("CAMPAIGN_NO_BOOK", "Avval kamida bitta kitob qo'shing.")
    campaign.status = status
    record_audit(
        session,
        actor_id=actor_id,
        action="CAMPAIGN_STATUS",
        entity_type="campaign",
        entity_id=campaign.id,
        after={"status": status.value},
    )
    await session.commit()
    if status == CampaignStatus.ACTIVE and announce:
        await announce_to_channel(session, campaign, actor_id=actor_id)
    return campaign


# ---------------------------------------------------------------------------- the channel post (isolated per contest)


async def announce_to_channel(session: AsyncSession, campaign: Campaign, *, actor_id: uuid.UUID | None = None) -> bool:
    """One announcement per contest (``dedup_key="campaign:<id>"``) — contests never share a post."""
    import html

    from app.models.enums import ChannelPostKind
    from app.services import channel

    books = await books_of(session, campaign.id)
    title = html.escape(campaign.name)
    lines = [f"📖 <b>{title}</b>", ""]
    if campaign.description:
        lines.append(html.escape(campaign.description))
        lines.append("")
    if books:
        lines.append("📚 Kitob(lar):")
        lines.extend(f"• <b>{html.escape(book.title)}</b> — {html.escape(book.author)}" for book in books)
        lines.append("")
    lines.append(f"🗓 {format_date(campaign.starts_at)} — {format_date(campaign.ends_at)}")
    lines.append("Botda «📖 Kitob tanlovlari» bo'limidan qatnashing!")
    cover = books[0].cover_key if books else None
    cover_url = books[0].cover_url if books else None
    posted = await channel.queue(
        session,
        kind=ChannelPostKind.CAMPAIGN,
        text="\n".join(lines),
        dedup_key=f"campaign:{campaign.id}",
        photo_key=cover,
        photo_url=cover_url if not cover else None,
        created_by=actor_id,
        automatic=False,
    )
    await session.commit()  # channel.queue only inserts; persist the post (and its dedup) now
    return posted


# ---------------------------------------------------------------------------- members take part


async def active_for_member(
    session: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Campaign, list[Book], ParticipantState]]:
    campaigns = list(
        await session.scalars(
            select(Campaign)
            .where(Campaign.deleted_at.is_(None), Campaign.status == CampaignStatus.ACTIVE)
            .order_by(Campaign.ends_at)
        )
    )
    mine = {
        participant.campaign_id: participant
        for participant in await session.scalars(
            select(CampaignParticipant).where(
                CampaignParticipant.user_id == user_id,
                CampaignParticipant.campaign_id.in_([campaign.id for campaign in campaigns]),
            )
        )
    }
    result = []
    for campaign in campaigns:
        participant = mine.get(campaign.id)
        state = ParticipantState(
            joined=participant is not None,
            completed=participant is not None and participant.completed_at is not None,
            verified=participant is not None and participant.verified_at is not None,
        )
        result.append((campaign, await books_of(session, campaign.id), state))
    return result


async def _active(session: AsyncSession, campaign_id: uuid.UUID) -> Campaign:
    campaign = await get(session, campaign_id)
    if campaign.status != CampaignStatus.ACTIVE:
        raise ConflictError("CAMPAIGN_NOT_ACTIVE", "Bu tanlov hozir faol emas.")
    return campaign


async def join(session: AsyncSession, *, user_id: uuid.UUID, campaign_id: uuid.UUID) -> None:
    await _active(session, campaign_id)
    await session.execute(
        insert(CampaignParticipant)
        .values(id=uuid.uuid4(), campaign_id=campaign_id, user_id=user_id)
        .on_conflict_do_nothing(constraint="uq_campaign_participant")
    )
    await session.commit()


async def mark_completed(session: AsyncSession, *, user_id: uuid.UUID, campaign_id: uuid.UUID) -> None:
    await _active(session, campaign_id)
    participant = await session.scalar(
        select(CampaignParticipant).where(
            CampaignParticipant.campaign_id == campaign_id, CampaignParticipant.user_id == user_id
        )
    )
    if participant is None:
        raise ConflictError("CAMPAIGN_NOT_JOINED", "Avval tanlovga qo'shiling.")
    if participant.completed_at is None:
        participant.completed_at = datetime.now(UTC)
    await session.commit()


# ---------------------------------------------------------------------------- admin confirms → points


async def verify(session: AsyncSession, *, actor_id: uuid.UUID, campaign_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from app.services.notifications import enqueue_notification
    from app.services.scoring import award_points

    campaign = await get(session, campaign_id)
    participant = await session.scalar(
        select(CampaignParticipant).where(
            CampaignParticipant.campaign_id == campaign_id, CampaignParticipant.user_id == user_id
        )
    )
    if participant is None:
        raise NotFoundError("CAMPAIGN_NOT_JOINED", "A'zo bu tanlovda qatnashmagan.")
    if participant.verified_at is not None:
        return  # already confirmed — idempotent
    book_count = len(await books_of(session, campaign.id))
    points = campaign.points_per_book * max(book_count, 1) + campaign.completion_bonus
    participant.completed_at = participant.completed_at or datetime.now(UTC)
    participant.verified_at = datetime.now(UTC)
    participant.verified_by = actor_id
    participant.points_awarded = True
    if points > 0:
        await award_points(
            session,
            user_id=user_id,
            amount=points,
            category=ScoreCategory.CAMPAIGN,
            idempotency_key=f"campaign:{campaign.id}:{user_id}",
            source_type="campaign",
            source_id=campaign.id,
            created_by=actor_id,
            reason=f"«{campaign.name}» tanlovi",
        )
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.REWARD,
            text=f"🎉 «{campaign.name}» tanlovini yakunladingiz! +{points} ball qo'shildi. Tabriklaymiz!",
            dedup_key=f"campaign_done:{campaign.id}:{user_id}",
            payload={"mood": "CELEBRATE"},
            priority=2,
        )
    record_audit(
        session,
        actor_id=actor_id,
        action="CAMPAIGN_VERIFY",
        entity_type="campaign",
        entity_id=campaign.id,
        after={"user_id": str(user_id), "points": points},
    )
    await session.commit()


# ---------------------------------------------------------------------------- the per-contest report


async def report(session: AsyncSession, campaign: Campaign) -> Any:
    from app.services.document_render import Document, Table
    from app.services.documents import _header
    from app.services.passport import member_number

    books = await books_of(session, campaign.id)
    rows = await participants(session, campaign.id)
    table_rows: list[list[Any]] = []
    for index, (participant, user) in enumerate(rows, start=1):
        if participant.verified_at is not None:
            state = "✅ tasdiqlangan"
        elif participant.completed_at is not None:
            state = "⏳ tekshirilmoqda"
        else:
            state = "📖 o'qimoqda"
        table_rows.append(
            [
                index,
                f"{user.last_name} {user.first_name}",
                member_number(user),
                user.group_name or "—",
                state,
                format_date(participant.verified_at) if participant.verified_at else "—",
            ]
        )
    verified = sum(1 for participant, _ in rows if participant.verified_at is not None)
    summary = Table(
        "Jami",
        ["Ko'rsatkich", "Qiymat"],
        [
            ["Kitob(lar)", ", ".join(book.title for book in books) or "—"],
            ["Qatnashchilar", str(len(rows))],
            ["Yakunlagan (tasdiqlangan)", str(verified)],
            ["Davr", f"{format_date(campaign.starts_at)} — {format_date(campaign.ends_at)}"],
        ],
    )
    detail = Table(
        "Qatnashchilar",
        ["№", "F.I.Sh.", "A'zo №", "Guruh", "Holat", "Tasdiqlandi"],
        table_rows,
    )
    safe_name = "".join(ch for ch in campaign.name if ch.isalnum() or ch in " -_").strip().replace(" ", "-")
    return Document(
        title=f"«{campaign.name}» — kitob tanlovi hisoboti",
        filename=f"tanlov-{safe_name or campaign.id.hex[:8]}",
        lines=await _header(session),
        tables=[summary, detail],
        signer=None,
    )
