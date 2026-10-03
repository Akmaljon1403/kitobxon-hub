"""Promo-code giveaways: the club hands out codes of a reward by a fair, recorded rule.

* ``RANDOM``       — random members of the audience; premium members get a double chance
  (when ``premium_bonus``). Club administrators never take part in a random draw.
* ``TEST_TOP``     — most test points earned in the period (e.g. «the month's best test-taker»).
* ``EVENT_PLACES`` — places 1..N of the test of every event held in the period, each event
  separately (four events a month = up to twelve winners).
* ``RANKING_TOP``  — the top N of the club ranking for the period.

A giveaway is drawn at once from the Admin Panel or automatically at ``scheduled_at`` (the
``giveaways_due`` job); ``repeat_monthly`` schedules the next month after each draw. Winners and
the random seed are stored, every winner gets a code through ``rewards.assign`` and, when
``announce`` is set, all members see the winners' list.
"""

from __future__ import annotations

import calendar
import random
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, BadRequestError, ConflictError, NotFoundError
from app.models import (
    AttendanceRecord,
    Event,
    Giveaway,
    Reward,
    RewardCode,
    Role,
    Test,
    User,
    UserRole,
)
from app.models.enums import (
    AttendanceStatus,
    GiveawayAudience,
    GiveawayRule,
    GiveawayStatus,
    NotificationType,
    RewardCodeStatus,
    RewardStatus,
    TestStatus,
    UserStatus,
)
from app.services import rewards as reward_service
from app.services.audit import record_audit
from app.services.notifications import app_button, enqueue_for_members, render
from app.services.settings import get_setting
from app.utils.timezone import MONTHS_UZ, local_tz

PREMIUM_WEIGHT = 2
MAX_EVENT_PLACES = 10
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
RULE_TITLES = {
    GiveawayRule.RANDOM: "🎲 Tasodifiy g'oliblar",
    GiveawayRule.TEST_TOP: "📝 Testlarda eng ko'p ball",
    GiveawayRule.EVENT_PLACES: "📅 Har bir tadbir testining o'rinlari",
    GiveawayRule.RANKING_TOP: "🏆 Reyting peshqadamlari",
}
_FIELDS = (
    "title",
    "reward_id",
    "rule",
    "audience",
    "winners_count",
    "premium_bonus",
    "period_start",
    "period_end",
    "scheduled_at",
    "announce",
    "repeat_monthly",
)


@dataclass
class Winner:
    user_id: uuid.UUID
    name: str  # as shown publicly (the ranking name format)
    full_name: str
    reason: str
    place: int | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "name": self.name,
            "full_name": self.full_name,
            "reason": self.reason,
            "place": self.place,
        }


@dataclass
class Draw:
    winners: list[Winner]
    eligible: int = 0  # RANDOM: members taking part
    premium: int = 0  # RANDOM: of them premium (double chance)
    notes: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


def window(giveaway: Giveaway) -> tuple[datetime, datetime]:
    """The period as [start, end) in the club's time zone, both dates included."""
    start = datetime.combine(giveaway.period_start, time.min, tzinfo=local_tz())
    end = datetime.combine(giveaway.period_end + timedelta(days=1), time.min, tzinfo=local_tz())
    return start, end


def period_label(start: date, end: date) -> str:
    if start.day == 1 and end == start.replace(day=calendar.monthrange(start.year, start.month)[1]):
        return f"{start.year}-yil {MONTHS_UZ[start.month - 1]}"
    if start == end:
        return f"{start:%d.%m.%Y}"
    return f"{start:%d.%m.%Y} — {end:%d.%m.%Y}"


def _add_month(value: date) -> date:
    year, month = (value.year + 1, 1) if value.month == 12 else (value.year, value.month + 1)
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


def next_period(start: date, end: date) -> tuple[date, date]:
    """The same period one month later; a whole calendar month moves to the whole next month."""
    whole_month = start.day == 1 and end.day == calendar.monthrange(end.year, end.month)[1] and start.month == end.month
    if whole_month:
        first = _add_month(start)
        return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return _add_month(start), _add_month(end)


async def _name_format(session: AsyncSession) -> str:
    return str(await get_setting(session, "ranking.public_name_format"))


def _public_name(user: User, name_format: str) -> str:
    from app.services.ranking import display_name

    return display_name(user.first_name, user.last_name or "", name_format)


def _full_name(user: User) -> str:
    return f"{user.last_name or ''} {user.first_name}".strip()


def _members(audience: GiveawayAudience, start: datetime, end: datetime) -> Any:
    """SELECT of user ids: active registered members of the audience."""
    from app.services.premium import premium_members

    query = select(User.id).where(
        User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), User.registered_at.is_not(None)
    )
    if audience == GiveawayAudience.ATTENDED:
        query = query.where(
            User.id.in_(
                select(AttendanceRecord.user_id)
                .join(Event, Event.id == AttendanceRecord.event_id)
                .where(
                    AttendanceRecord.status == AttendanceStatus.VERIFIED,
                    Event.deleted_at.is_(None),
                    Event.starts_at >= start,
                    Event.starts_at < end,
                )
            )
        )
    elif audience == GiveawayAudience.PREMIUM:
        query = query.where(User.id.in_(premium_members()))
    return query


def _staff() -> Any:
    from app.services.rbac import ADMIN_ROLES

    return select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.code.in_(ADMIN_ROLES))


async def _users(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    return {user.id: user for user in await session.scalars(select(User).where(User.id.in_(ids)))}


# ---------------------------------------------------------------------------- the rules


async def _random(session: AsyncSession, giveaway: Giveaway, seed: str) -> Draw:
    from app.services.premium import premium_members

    start, end = window(giveaway)
    ids = sorted(
        await session.scalars(_members(giveaway.audience, start, end).where(User.id.not_in(_staff()))), key=str
    )
    premium = set(await session.scalars(premium_members().where(User.id.in_(ids)))) if ids else set()
    rng = random.Random(seed)  # noqa: S311 - the seed comes from `secrets` and is published for checking
    # Weighted sampling without replacement (Efraimidis–Spirakis): the k largest u^(1/w).
    keyed = []
    for user_id in ids:
        weight = PREMIUM_WEIGHT if giveaway.premium_bonus and user_id in premium else 1
        keyed.append((rng.random() ** (1 / weight), user_id))
    chosen = [user_id for _, user_id in sorted(keyed, reverse=True)[: giveaway.winners_count]]
    users = await _users(session, chosen)
    name_format = await _name_format(session)
    winners = [
        Winner(
            user_id=user_id,
            name=_public_name(users[user_id], name_format),
            full_name=_full_name(users[user_id]),
            reason="Tasodifiy g'olib"
            + (" (💎 ikki baravar imkoniyat)" if user_id in premium and giveaway.premium_bonus else ""),
        )
        for user_id in chosen
    ]
    return Draw(winners=winners, eligible=len(ids), premium=len(premium))


async def _test_top(session: AsyncSession, giveaway: Giveaway) -> Draw:
    from app.services.ranking import _aggregate

    start, end = window(giveaway)
    aggregate = (await _aggregate(session, "all", between=(start, end))).subquery()
    rows = (
        await session.execute(
            select(aggregate.c.user_id, aggregate.c.tests)
            .where(aggregate.c.tests > 0, aggregate.c.user_id.in_(_members(giveaway.audience, start, end)))
            .order_by(
                aggregate.c.tests.desc(), aggregate.c.total.desc(), aggregate.c.last_at.asc(), aggregate.c.user_id
            )
            .limit(giveaway.winners_count)
        )
    ).all()
    users = await _users(session, [row.user_id for row in rows])
    name_format = await _name_format(session)
    return Draw(
        winners=[
            Winner(
                user_id=row.user_id,
                name=_public_name(users[row.user_id], name_format),
                full_name=_full_name(users[row.user_id]),
                reason=f"Testlarda {int(row.tests)} ball — {place}-o'rin",
                place=place,
            )
            for place, row in enumerate(rows, start=1)
        ]
    )


async def _event_places(session: AsyncSession, giveaway: Giveaway) -> Draw:
    from app.services import quizzes

    start, end = window(giveaway)
    rows = (
        await session.execute(
            select(Test, Event)
            .join(Event, Event.id == Test.event_id)
            .where(
                Test.deleted_at.is_(None),
                Event.deleted_at.is_(None),
                Test.status.in_((TestStatus.PUBLISHED, TestStatus.CLOSED)),
                Event.starts_at >= start,
                Event.starts_at < end,
            )
            .order_by(Event.starts_at, Test.starts_at)
        )
    ).all()
    tests_per_event: dict[uuid.UUID, int] = {}
    for _, event in rows:
        tests_per_event[event.id] = tests_per_event.get(event.id, 0) + 1
    draw = Draw(winners=[])
    picks: list[tuple[uuid.UUID, str, int]] = []
    for test, event in rows:
        label = f"«{event.title}»" + (f" ({test.title})" if tests_per_event[event.id] > 1 else "")
        if test.status != TestStatus.CLOSED:
            draw.notes.append(f"{label} testi hali yopilmagan — hisobga olinmaydi.")
            continue
        present = set(
            await session.scalars(
                select(AttendanceRecord.user_id).where(
                    AttendanceRecord.event_id == event.id, AttendanceRecord.status == AttendanceStatus.VERIFIED
                )
            )
        )
        standings = [row for row in await quizzes.test_standings(session, test) if row["user_id"] in present]
        if not standings:
            draw.notes.append(f"{label}: testdan o'tgan qatnashchi yo'q.")
        for place, row in enumerate(standings[: giveaway.winners_count], start=1):
            picks.append((row["user_id"], f"{label} — {place}-o'rin", place))
    if not rows:
        draw.notes.append("Bu davrda testi bor tadbir topilmadi.")
    users = await _users(session, [user_id for user_id, _, _ in picks])
    name_format = await _name_format(session)
    draw.winners = [
        Winner(
            user_id=user_id,
            name=_public_name(users[user_id], name_format),
            full_name=_full_name(users[user_id]),
            reason=reason,
            place=place,
        )
        for user_id, reason, place in picks
        if users[user_id].status == UserStatus.ACTIVE and users[user_id].deleted_at is None
    ]
    return draw


async def _ranking_top(session: AsyncSession, giveaway: Giveaway) -> Draw:
    from app.services.ranking import ranking

    start, end = window(giveaway)
    board = await ranking(
        session, period="all", scope="all", viewer=None, limit=giveaway.winners_count * 5 + 50, between=(start, end)
    )
    allowed = set(await session.scalars(_members(giveaway.audience, start, end)))
    rows = [row for row in board.items if row.user_id in allowed][: giveaway.winners_count]
    users = await _users(session, [row.user_id for row in rows])
    return Draw(
        winners=[
            Winner(
                user_id=row.user_id,
                name=row.name,
                full_name=_full_name(users[row.user_id]),
                reason=f"Reytingda {row.rank}-o'rin ({row.total} ball)",
                place=place,
            )
            for place, row in enumerate(rows, start=1)
        ]
    )


async def pick(session: AsyncSession, giveaway: Giveaway, seed: str) -> Draw:
    rule = GiveawayRule(giveaway.rule)
    if rule == GiveawayRule.RANDOM:
        return await _random(session, giveaway, seed)
    if rule == GiveawayRule.TEST_TOP:
        return await _test_top(session, giveaway)
    if rule == GiveawayRule.EVENT_PLACES:
        return await _event_places(session, giveaway)
    return await _ranking_top(session, giveaway)


# ---------------------------------------------------------------------------- admin


async def get(session: AsyncSession, giveaway_id: uuid.UUID) -> Giveaway:
    giveaway = await session.get(Giveaway, giveaway_id)
    if giveaway is None:
        raise NotFoundError("GIVEAWAY_NOT_FOUND", "Sovg'a o'yini topilmadi.")
    return giveaway


async def codes_available(session: AsyncSession, reward_id: uuid.UUID) -> int | None:
    """Unused, unexpired codes of the reward; None when the reward has no codes at all."""
    total = await session.scalar(select(func.count()).select_from(RewardCode).where(RewardCode.reward_id == reward_id))
    if not total:
        return None
    return int(
        await session.scalar(
            select(func.count())
            .select_from(RewardCode)
            .where(
                RewardCode.reward_id == reward_id,
                RewardCode.status == RewardCodeStatus.AVAILABLE,
                or_(RewardCode.expires_at.is_(None), RewardCode.expires_at > _now()),
            )
        )
        or 0
    )


async def _validate(session: AsyncSession, giveaway: Giveaway) -> None:
    reward = await reward_service.get_reward(session, giveaway.reward_id)
    if reward.status != RewardStatus.ACTIVE:
        raise BadRequestError("REWARD_NOT_ACTIVE", "Faol sovg'ani tanlang.")
    if giveaway.period_end < giveaway.period_start:
        raise BadRequestError("PERIOD_ORDER", "Davr oxiri boshidan oldin bo'lishi mumkin emas.")
    limit = MAX_EVENT_PLACES if giveaway.rule == GiveawayRule.EVENT_PLACES else 100
    if not 1 <= giveaway.winners_count <= limit:
        raise BadRequestError("WINNERS_COUNT", f"G'oliblar soni 1 dan {limit} gacha bo'lishi kerak.")
    if giveaway.scheduled_at is not None:
        giveaway.status = GiveawayStatus.SCHEDULED
    elif giveaway.status == GiveawayStatus.SCHEDULED:
        giveaway.status = GiveawayStatus.DRAFT


def _snapshot(giveaway: Giveaway) -> dict[str, Any]:
    return {
        "title": giveaway.title,
        "rule": str(giveaway.rule),
        "winners_count": giveaway.winners_count,
        "period": f"{giveaway.period_start}..{giveaway.period_end}",
        "scheduled_at": giveaway.scheduled_at.isoformat() if giveaway.scheduled_at else None,
        "status": str(giveaway.status),
    }


async def create(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> Giveaway:
    giveaway = Giveaway(**{key: value for key, value in data.items() if key in _FIELDS}, created_by=actor_id)
    if giveaway.scheduled_at is not None and giveaway.scheduled_at <= _now():
        raise BadRequestError("SCHEDULE_IN_PAST", "O'tkazish vaqti kelajakda bo'lishi kerak.")
    giveaway.status = GiveawayStatus.DRAFT
    await _validate(session, giveaway)
    session.add(giveaway)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="GIVEAWAY_CREATE",
        entity_type="giveaway",
        entity_id=giveaway.id,
        after=_snapshot(giveaway),
    )
    await session.commit()
    return giveaway


async def update(
    session: AsyncSession, *, actor_id: uuid.UUID, giveaway_id: uuid.UUID, changes: dict[str, Any]
) -> Giveaway:
    giveaway = await get(session, giveaway_id)
    if giveaway.status not in (GiveawayStatus.DRAFT, GiveawayStatus.SCHEDULED):
        raise ConflictError("GIVEAWAY_CLOSED", "O'tkazilgan yoki bekor qilingan o'yinni o'zgartirib bo'lmaydi.")
    before = _snapshot(giveaway)
    for key, value in changes.items():
        if key in _FIELDS:
            setattr(giveaway, key, value)
    if "scheduled_at" in changes and giveaway.scheduled_at is not None and giveaway.scheduled_at <= _now():
        raise BadRequestError("SCHEDULE_IN_PAST", "O'tkazish vaqti kelajakda bo'lishi kerak.")
    await _validate(session, giveaway)
    record_audit(
        session,
        actor_id=actor_id,
        action="GIVEAWAY_UPDATE",
        entity_type="giveaway",
        entity_id=giveaway.id,
        before=before,
        after=_snapshot(giveaway),
    )
    await session.commit()
    return giveaway


async def cancel(session: AsyncSession, *, actor_id: uuid.UUID, giveaway_id: uuid.UUID) -> Giveaway:
    giveaway = await get(session, giveaway_id)
    if giveaway.status not in (GiveawayStatus.DRAFT, GiveawayStatus.SCHEDULED):
        raise ConflictError("GIVEAWAY_CLOSED", "Bu o'yin allaqachon o'tkazilgan yoki bekor qilingan.")
    giveaway.status = GiveawayStatus.CANCELLED
    record_audit(session, actor_id=actor_id, action="GIVEAWAY_CANCEL", entity_type="giveaway", entity_id=giveaway.id)
    await session.commit()
    return giveaway


async def list_all(session: AsyncSession) -> list[tuple[Giveaway, str, int | None]]:
    """(giveaway, reward title, codes still available)."""
    rows = (
        await session.execute(
            select(Giveaway, Reward.title)
            .join(Reward, Reward.id == Giveaway.reward_id)
            .order_by(
                (Giveaway.status.in_((GiveawayStatus.DRAFT, GiveawayStatus.SCHEDULED))).desc(),
                func.coalesce(Giveaway.drawn_at, Giveaway.scheduled_at, Giveaway.created_at).desc(),
            )
            .limit(200)
        )
    ).all()
    codes: dict[uuid.UUID, int | None] = {}
    for giveaway, _ in rows:
        if giveaway.reward_id not in codes:
            codes[giveaway.reward_id] = await codes_available(session, giveaway.reward_id)
    return [(giveaway, title, codes[giveaway.reward_id]) for giveaway, title in rows]


async def preview(session: AsyncSession, giveaway_id: uuid.UUID) -> dict[str, Any]:
    """Who would win if the giveaway were drawn now (RANDOM: only how many take part)."""
    giveaway = await get(session, giveaway_id)
    draw = await pick(session, giveaway, seed="preview")
    available = await codes_available(session, giveaway.reward_id)
    random_rule = giveaway.rule == GiveawayRule.RANDOM
    notes = list(draw.notes)
    expected = min(giveaway.winners_count, draw.eligible) if random_rule else len(draw.winners)
    if available is not None and available < expected:
        notes.append(f"Kodlar yetmaydi: kerak {expected} ta, bor {available} ta. Avval kod qo'shing.")
    return {
        "eligible": draw.eligible if random_rule else len(draw.winners),
        "premium": draw.premium,
        "winners": [] if random_rule else [winner.as_json() for winner in draw.winners],
        "codes_available": available,
        "notes": notes,
    }


async def _notify_admins(session: AsyncSession, giveaway: Giveaway, text: str, key: str) -> None:
    from app.services.rbac import super_admins

    members = super_admins()
    if giveaway.created_by is not None:
        members = members.union(select(User.id).where(User.id == giveaway.created_by))
    await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=(await render(session, NotificationType.SYSTEM, message=text)) or text,
        dedup_prefix=f"giveaway:{giveaway.id}:{key}",
        members=members,
        payload={"buttons": [{"text": "🎲 Sovg'a o'yinlari", "admin_route": "giveaways"}]},
        priority=2,
    )


async def draw(session: AsyncSession, *, actor_id: uuid.UUID | None, giveaway_id: uuid.UUID) -> Giveaway:
    """Choose the winners and hand out the codes. Raises (and changes nothing) when there are no
    winners or not enough codes, so the admin can fix it and draw again."""
    giveaway = await session.scalar(select(Giveaway).where(Giveaway.id == giveaway_id).with_for_update())
    if giveaway is None:
        raise NotFoundError("GIVEAWAY_NOT_FOUND", "Sovg'a o'yini topilmadi.")
    if giveaway.status not in (GiveawayStatus.DRAFT, GiveawayStatus.SCHEDULED):
        raise ConflictError("GIVEAWAY_CLOSED", "Bu o'yin allaqachon o'tkazilgan yoki bekor qilingan.")
    reward = await reward_service.get_reward(session, giveaway.reward_id)
    if reward.status != RewardStatus.ACTIVE or (reward.expires_at and reward.expires_at <= _now()):
        raise ConflictError("REWARD_NOT_ACTIVE", f"«{reward.title}» sovg'asi faol emas yoki muddati o'tgan.")
    seed = secrets.token_hex(16)
    result = await pick(session, giveaway, seed)
    if not result.winners:
        raise ConflictError("NO_WINNERS", "Shartlarga mos g'olib topilmadi. " + " ".join(result.notes))
    available = await codes_available(session, giveaway.reward_id)
    if available is not None and available < len(result.winners):
        raise ConflictError(
            "NO_CODES_LEFT",
            f"«{reward.title}» uchun kodlar yetmaydi: kerak {len(result.winners)} ta, bor {available} ta.",
        )

    # Record the outcome first: a second click (or worker) now sees DONE and stops.
    giveaway.status = GiveawayStatus.DONE
    giveaway.drawn_at = _now()
    giveaway.seed = seed if giveaway.rule == GiveawayRule.RANDOM else None
    giveaway.results = [winner.as_json() for winner in result.winners]
    record_audit(
        session,
        actor_id=actor_id,
        action="GIVEAWAY_DRAW",
        entity_type="giveaway",
        entity_id=giveaway.id,
        after={"winners": len(result.winners), "seed": giveaway.seed},
    )
    await session.commit()

    # A failed assignment rolls the session back, so nothing below reads expired ORM objects.
    label = period_label(giveaway.period_start, giveaway.period_end)
    title, reward_title, reward_id = giveaway.title, reward.title, giveaway.reward_id
    assigned_by = actor_id or giveaway.created_by
    results = []
    for index, winner in enumerate(result.winners):
        entry = winner.as_json()
        try:
            user_reward = await reward_service.assign(
                session,
                actor_id=assigned_by,  # type: ignore[arg-type]
                reward_id=reward_id,
                user_id=winner.user_id,
                note=f"🎲 {title}: {winner.reason}",
                idempotency_key=f"giveaway:{giveaway_id}:{index}",
                allow_repeat=True,
                message=(
                    f"🎉 Tabriklaymiz! Siz «{title}» ({label}) g'olibisiz!\n"
                    f"🏅 {winner.reason}\n🎁 Sovg'angiz: «{reward_title}»\n\n"
                    "Kodni ilovadagi «🎁 Sovg'alarim» bo'limida ko'rasiz."
                ),
            )
            entry["user_reward_id"] = str(user_reward.id)
        except AppError as error:
            await session.rollback()
            entry["error"] = error.message
        results.append(entry)
    giveaway = await get(session, giveaway_id)
    giveaway.results = results
    if giveaway.announce:
        await _announce(session, giveaway, results)
    if giveaway.repeat_monthly:
        await _schedule_next(session, giveaway)
    await session.commit()
    return giveaway


def winners_text(giveaway: Giveaway, results: list[dict[str, Any]]) -> str:
    label = period_label(giveaway.period_start, giveaway.period_end)
    lines = [f"🎉 «{giveaway.title}» g'oliblari ({label}):", ""]
    for entry in results:
        if entry.get("error"):
            continue
        medal = MEDALS.get(entry.get("place") or 0, "🎁") if giveaway.rule != GiveawayRule.RANDOM else "🎁"
        lines.append(f"{medal} {entry['name']} — {entry['reason']}")
    lines += ["", "Tabriklaymiz! Keyingi safar siz ham g'olib bo'lishingiz mumkin — kitob o'qishda davom eting 📚"]
    return "\n".join(lines)


async def _announce(session: AsyncSession, giveaway: Giveaway, results: list[dict[str, Any]]) -> None:
    text = winners_text(giveaway, results)
    await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=(await render(session, NotificationType.SYSTEM, message=text)) or text,
        dedup_prefix=f"giveaway:{giveaway.id}:announce",
        payload=app_button("rewards", "🎁 Sovg'alar"),
    )
    from app.services import channel

    await channel.giveaway_results(session, giveaway.id, text)


async def _schedule_next(session: AsyncSession, giveaway: Giveaway) -> None:
    start, end = next_period(giveaway.period_start, giveaway.period_end)
    exists = await session.scalar(
        select(Giveaway.id).where(
            Giveaway.reward_id == giveaway.reward_id,
            Giveaway.rule == giveaway.rule,
            Giveaway.period_start == start,
            Giveaway.title == giveaway.title,
            Giveaway.status != GiveawayStatus.CANCELLED,
        )
    )
    if exists is not None:
        return
    when = giveaway.scheduled_at or giveaway.drawn_at or _now()
    local = when.astimezone(local_tz())
    next_when = datetime.combine(_add_month(local.date()), local.timetz())
    session.add(
        Giveaway(
            **{
                key: getattr(giveaway, key)
                for key in _FIELDS
                if key not in ("period_start", "period_end", "scheduled_at")
            },
            period_start=start,
            period_end=end,
            scheduled_at=max(next_when, _now() + timedelta(hours=1)),
            status=GiveawayStatus.SCHEDULED,
            created_by=giveaway.created_by,
        )
    )


async def run_due(session: AsyncSession) -> int:
    """Scheduler job: draw scheduled giveaways whose time has come. A giveaway that cannot be drawn
    (no codes, no winners) stays scheduled and the admins are told once; it is retried next minute."""
    due = list(
        await session.scalars(
            select(Giveaway.id)
            .where(Giveaway.status == GiveawayStatus.SCHEDULED, Giveaway.scheduled_at <= _now())
            .order_by(Giveaway.scheduled_at)
        )
    )
    drawn = 0
    for giveaway_id in due:
        try:
            await draw(session, actor_id=None, giveaway_id=giveaway_id)
            drawn += 1
        except AppError as error:
            await session.rollback()
            giveaway = await get(session, giveaway_id)
            await _notify_admins(
                session,
                giveaway,
                f"⚠️ «{giveaway.title}» sovg'a o'yinini avtomatik o'tkazib bo'lmadi: {error.message}\n"
                "Muammo hal qilinsa, o'yin o'zi o'tkaziladi (yoki admin paneldan qo'lda o'tkazing).",
                key=f"failed:{error.code}",
            )
            await session.commit()
    return drawn


# ---------------------------------------------------------------------------- members


async def for_members(session: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """Upcoming giveaways and the winners of the last 60 days (public names only)."""
    rows = (
        await session.execute(
            select(Giveaway, Reward.title)
            .join(Reward, Reward.id == Giveaway.reward_id)
            .where(
                or_(
                    Giveaway.status == GiveawayStatus.SCHEDULED,
                    (Giveaway.status == GiveawayStatus.DONE) & (Giveaway.drawn_at >= _now() - timedelta(days=60)),
                )
            )
            .order_by(func.coalesce(Giveaway.scheduled_at, Giveaway.drawn_at))
        )
    ).all()
    upcoming, recent = [], []
    for giveaway, reward_title in rows:
        item = {
            "id": giveaway.id,
            "title": giveaway.title,
            "reward": reward_title,
            "rule": giveaway.rule,
            "rule_title": RULE_TITLES[GiveawayRule(giveaway.rule)],
            "winners_count": giveaway.winners_count,
            "period": period_label(giveaway.period_start, giveaway.period_end),
            "premium_bonus": giveaway.premium_bonus and giveaway.rule == GiveawayRule.RANDOM,
            "audience": giveaway.audience,
            "scheduled_at": giveaway.scheduled_at,
            "drawn_at": giveaway.drawn_at,
            "winners": [
                {"name": entry["name"], "reason": entry["reason"], "place": entry.get("place")}
                for entry in (giveaway.results or [])
                if not entry.get("error")
            ],
        }
        (upcoming if giveaway.status == GiveawayStatus.SCHEDULED else recent).append(item)
    recent.reverse()
    return {"upcoming": upcoming, "recent": recent}
