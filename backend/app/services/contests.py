"""Referral contests: «kim <sana>gacha klubga eng ko'p yangi kitobxon olib kelsa — sovg'a».

The administrator chooses the period, which invited friends count (registered, came to an event,
or earned points), the prize of each place (points, Premium days, a promo code of a reward, or a
prize handed over in person), a prize for everyone who reaches the minimum, and what members see
while it runs (the table, the counts, the names, their own place, the prizes; the table can be
hidden for the final hours). The ``referral_contests`` job announces the start, reminds before the
end and, at the end, chooses the winners, gives the prizes and tells everybody.
"""

from __future__ import annotations

import html
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, BadRequestError, ConflictError, NotFoundError
from app.models import Faculty, ReferralContest, Reward, ScoreTransaction, User
from app.models.enums import (
    ChannelPostKind,
    ContestRule,
    ContestStatus,
    NotificationType,
    PremiumSource,
    RewardStatus,
    ScoreCategory,
    UserStatus,
)
from app.services.audit import record_audit
from app.services.notifications import app_button, celebrate, enqueue_for_members, enqueue_notification
from app.utils.timezone import format_datetime

logger = logging.getLogger(__name__)

ROUTE = "invite"
RECENT_RESULTS = timedelta(days=14)  # finished contests stay on the members' page this long
EDITABLE_WHILE_RUNNING = {
    "title",
    "description",
    "ends_at",
    "show_leaderboard",
    "leaderboard_size",
    "show_counts",
    "name_format",
    "show_my_place",
    "show_prizes",
    "freeze_hours",
    "remind_hours",
    "announce_results",
    "post_to_channel",
}
RULE_TEXT = {
    ContestRule.REGISTERED: "havolangiz orqali ro'yxatdan o'tgan do'stlar",
    ContestRule.ATTENDED: "havolangiz orqali qo'shilib, kamida bitta tadbirga kelgan do'stlar",
    ContestRule.POINTS: "havolangiz orqali qo'shilib, kamida {points} ball to'plagan do'stlar",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _e(value: str) -> str:
    """Safe in the bot's HTML; apostrophes (o'rin, do'st) stay as they are."""
    return html.escape(value, quote=False)


def rule_text(contest: ReferralContest) -> str:
    return RULE_TEXT[ContestRule(contest.rule)].format(points=contest.min_friend_points)


def running(contest: ReferralContest, now: datetime | None = None) -> bool:
    now = now or _now()
    return contest.status == ContestStatus.PUBLISHED and contest.starts_at <= now < contest.ends_at


def frozen(contest: ReferralContest, now: datetime | None = None) -> bool:
    """The table is hidden in the final hours (the intrigue of the last day)."""
    now = now or _now()
    return bool(contest.freeze_hours) and contest.ends_at - timedelta(hours=contest.freeze_hours) <= now


def prize_text(prize: dict[str, Any] | None, rewards: dict[str, str] | None = None) -> str:
    if not prize:
        return ""
    parts = []
    if prize.get("points"):
        parts.append(f"+{prize['points']} ball")
    if prize.get("premium_days"):
        parts.append(f"{prize['premium_days']} kunlik 💎 Premium")
    if prize.get("reward_id"):
        parts.append(f"🎁 {(rewards or {}).get(str(prize['reward_id']), 'sovg`a kodi')}")
    if prize.get("text"):
        parts.append(str(prize["text"]))
    return " + ".join(parts)


def _prize_for(contest: ReferralContest, place: int) -> dict[str, Any] | None:
    return next((prize for prize in contest.prizes or [] if int(prize.get("place", 0)) == place), None)


def name_of(first_name: str, last_name: str, name_format: str) -> str:
    from app.services.ranking import display_name

    return display_name(first_name, last_name, "SHORT" if name_format == "HIDDEN" else name_format)


# ---------------------------------------------------------------------------- the table


@dataclass(frozen=True)
class Standing:
    place: int
    user_id: uuid.UUID
    first_name: str
    last_name: str
    faculty: str | None
    group_name: str | None
    friends: int


def _excluded_ids(contest: ReferralContest) -> set[uuid.UUID]:
    return {uuid.UUID(str(item["user_id"])) for item in contest.excluded or []}


def eligible_conditions(contest: ReferralContest) -> list[Any]:
    """Who may take part: active members (not administrators) of the chosen faculty / course."""
    from app.services.referrals import not_staff

    conditions: list[Any] = [User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), not_staff(User.id)]
    if contest.faculty_id is not None:
        conditions.append(User.faculty_id == contest.faculty_id)
    if contest.course is not None:
        conditions.append(User.course == contest.course)
    excluded = _excluded_ids(contest)
    if excluded:
        conditions.append(User.id.not_in(excluded))
    return conditions


async def standings(session: AsyncSession, contest: ReferralContest, *, limit: int | None = None) -> list[Standing]:
    """Participants with at least one counted friend, best first. Ties: who reached the number first,
    then who joined the club earlier."""
    from app.services.referrals import inviters

    counted = inviters(
        rule=ContestRule(contest.rule).value,
        joined_from=contest.starts_at,
        joined_until=contest.ends_at,
        min_friend_points=contest.min_friend_points,
        counted_until=contest.ends_at,
    ).subquery()
    statement = (
        select(
            User.id,
            User.first_name,
            User.last_name,
            Faculty.name,
            User.group_name,
            counted.c.friends,
        )
        .join(User, User.id == counted.c.user_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .where(*eligible_conditions(contest))
        .order_by(counted.c.friends.desc(), counted.c.last_joined_at.asc(), User.registered_at.asc(), User.id)
    )
    if limit is not None:
        statement = statement.limit(limit)
    rows = await session.execute(statement)
    return [
        Standing(place, row[0], row[1], row[2], row[3], row[4], int(row[5])) for place, row in enumerate(rows, start=1)
    ]


async def friends_of(session: AsyncSession, contest: ReferralContest, user_id: uuid.UUID) -> list[dict[str, Any]]:
    """The administrator's check: every friend a participant brought in the period, and whether they count."""

    from app.services.referrals import came_to_event

    points = (
        select(func.coalesce(func.sum(ScoreTransaction.amount), 0))
        .where(ScoreTransaction.user_id == User.id, ScoreTransaction.created_at < contest.ends_at)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            User.phone,
            User.registered_at,
            User.status,
            came_to_event(User.id, contest.ends_at),
            points,
        )
        .where(
            User.referred_by == user_id,
            User.deleted_at.is_(None),
            User.registered_at >= contest.starts_at,
            User.registered_at < contest.ends_at,
        )
        .order_by(User.registered_at)
    )
    result = []
    for friend_id, first, last, phone, joined, status, came, friend_points in rows:
        counts = status == UserStatus.ACTIVE and (
            contest.rule == ContestRule.REGISTERED
            or (contest.rule == ContestRule.ATTENDED and bool(came))
            or (contest.rule == ContestRule.POINTS and int(friend_points) >= max(contest.min_friend_points, 1))
        )
        result.append(
            {
                "user_id": friend_id,
                "name": f"{last} {first}",
                "phone": phone,
                "joined_at": joined,
                "status": str(status),
                "came_to_event": bool(came),
                "points": int(friend_points),
                "counts": counts,
            }
        )
    return result


# ---------------------------------------------------------------------------- administration


def _check(contest: ReferralContest) -> None:
    if contest.ends_at <= contest.starts_at:
        raise BadRequestError("CONTEST_PERIOD", "Tugash vaqti boshlanishidan keyin bo'lsin.")
    places = [int(prize.get("place", 0)) for prize in contest.prizes or []]
    if any(place < 1 or place > contest.winners_count for place in places) or len(places) != len(set(places)):
        raise BadRequestError(
            "CONTEST_PRIZES", f"Sovrinlar 1–{contest.winners_count}-o'rinlar uchun, har biriga bittadan bo'lsin."
        )
    if contest.rule == ContestRule.POINTS and contest.min_friend_points < 1:
        raise BadRequestError("CONTEST_POINTS", "Do'st nechta ball to'plashi kerakligini yozing.")


async def _check_rewards(session: AsyncSession, contest: ReferralContest) -> None:
    for prize in contest.prizes or []:
        if prize.get("reward_id"):
            reward = await session.get(Reward, uuid.UUID(str(prize["reward_id"])))
            if reward is None or reward.status != RewardStatus.ACTIVE:
                raise BadRequestError("CONTEST_REWARD", "Tanlangan sovg'a topilmadi yoki faol emas.")


def _clean_prizes(prizes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for prize in prizes:
        item = {
            "place": int(prize["place"]),
            "points": int(prize.get("points") or 0),
            "premium_days": int(prize.get("premium_days") or 0),
            "reward_id": str(prize["reward_id"]) if prize.get("reward_id") else None,
            "text": (str(prize.get("text") or "").strip()[:200] or None),
        }
        if item["points"] or item["premium_days"] or item["reward_id"] or item["text"]:
            cleaned.append(item)
    return sorted(cleaned, key=lambda item: item["place"])


async def get(session: AsyncSession, contest_id: uuid.UUID) -> ReferralContest:
    contest = await session.get(ReferralContest, contest_id)
    if contest is None:
        raise NotFoundError("CONTEST_NOT_FOUND", "Tanlov topilmadi.")
    return contest


async def create(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> ReferralContest:
    data = {**data, "prizes": _clean_prizes(data.get("prizes") or [])}
    contest = ReferralContest(**data, created_by=actor_id, status=ContestStatus.DRAFT)
    _check(contest)
    await _check_rewards(session, contest)
    session.add(contest)
    await session.flush()
    record_audit(
        session, actor_id=actor_id, action="CONTEST_CREATE", entity_type="referral_contest", entity_id=contest.id
    )
    await session.commit()
    await session.refresh(contest)
    return contest


async def update(
    session: AsyncSession, *, actor_id: uuid.UUID, contest_id: uuid.UUID, changes: dict[str, Any]
) -> ReferralContest:
    contest = await get(session, contest_id)
    if contest.status in (ContestStatus.FINISHED, ContestStatus.CANCELLED):
        raise ConflictError("CONTEST_CLOSED", "Tugagan yoki bekor qilingan tanlovni o'zgartirib bo'lmaydi.")
    started = contest.status == ContestStatus.PUBLISHED and contest.starts_at <= _now()
    if started:
        locked = set(changes) - EDITABLE_WHILE_RUNNING
        if locked:
            raise ConflictError(
                "CONTEST_RUNNING",
                "Tanlov boshlangan: shartlar va sovrinlarni o'zgartirib bo'lmaydi (adolat uchun). "
                "Nomi, tavsifi, ko'rinish sozlamalari va tugash vaqtini o'zgartirish mumkin.",
            )
        if "ends_at" in changes and changes["ends_at"] <= _now():
            raise BadRequestError("CONTEST_PERIOD", "Tugash vaqti hozirdan keyin bo'lsin.")
    if "prizes" in changes:
        changes["prizes"] = _clean_prizes(changes["prizes"] or [])
    before = {key: str(getattr(contest, key)) for key in changes}
    for key, value in changes.items():
        setattr(contest, key, value)
    if "ends_at" in changes:
        contest.reminded_at = None  # a new end gets its own reminder
    _check(contest)
    await _check_rewards(session, contest)
    record_audit(
        session,
        actor_id=actor_id,
        action="CONTEST_UPDATE",
        entity_type="referral_contest",
        entity_id=contest.id,
        before=before,
        after={key: str(value) for key, value in changes.items()},
    )
    await session.commit()
    await session.refresh(contest)
    return contest


async def publish(session: AsyncSession, *, actor_id: uuid.UUID, contest_id: uuid.UUID) -> ReferralContest:
    contest = await get(session, contest_id)
    if contest.status != ContestStatus.DRAFT:
        raise ConflictError("CONTEST_NOT_DRAFT", "Faqat qoralama tanlovni e'lon qilish mumkin.")
    if contest.ends_at <= _now():
        raise BadRequestError("CONTEST_PERIOD", "Tugash vaqti o'tib ketgan.")
    _check(contest)
    contest.status = ContestStatus.PUBLISHED
    record_audit(
        session, actor_id=actor_id, action="CONTEST_PUBLISH", entity_type="referral_contest", entity_id=contest.id
    )
    await session.commit()
    if contest.starts_at <= _now():
        await _announce_start(session, contest)
        await session.commit()
    await session.refresh(contest)
    return contest


async def cancel(session: AsyncSession, *, actor_id: uuid.UUID, contest_id: uuid.UUID, reason: str) -> ReferralContest:
    contest = await get(session, contest_id)
    if contest.status in (ContestStatus.FINISHED, ContestStatus.CANCELLED):
        raise ConflictError("CONTEST_CLOSED", "Bu tanlov allaqachon yopilgan.")
    announced = contest.announced_at is not None
    contest.status = ContestStatus.CANCELLED
    record_audit(
        session,
        actor_id=actor_id,
        action="CONTEST_CANCEL",
        entity_type="referral_contest",
        entity_id=contest.id,
        reason=reason,
    )
    if announced:
        text = f"ℹ️ «{_e(contest.title)}» tanlovi bekor qilindi."
        if reason.strip():
            text += f"\nSabab: {_e(reason.strip())}"
        await enqueue_for_members(
            session,
            type_=NotificationType.ANNOUNCEMENT,
            text=text,
            dedup_prefix=f"contest:{contest.id}:cancelled",
            priority=4,
        )
    await session.commit()
    await session.refresh(contest)
    return contest


async def set_excluded(
    session: AsyncSession, *, actor_id: uuid.UUID, contest_id: uuid.UUID, user_id: uuid.UUID, reason: str | None
) -> ReferralContest:
    """``reason`` None puts a member back; otherwise removes them from the table (e.g. fake friends)."""
    contest = await get(session, contest_id)
    if contest.status in (ContestStatus.FINISHED, ContestStatus.CANCELLED):
        raise ConflictError("CONTEST_CLOSED", "Tanlov yopilgan.")
    others = [item for item in contest.excluded or [] if str(item["user_id"]) != str(user_id)]
    if reason is not None:
        if len(reason.strip()) < 3:
            raise BadRequestError("REASON_REQUIRED", "Sababini yozing.")
        others.append({"user_id": str(user_id), "reason": reason.strip()[:300]})
    contest.excluded = others
    record_audit(
        session,
        actor_id=actor_id,
        action="CONTEST_EXCLUDE" if reason is not None else "CONTEST_INCLUDE",
        entity_type="referral_contest",
        entity_id=contest.id,
        after={"user_id": str(user_id)},
        reason=reason,
    )
    await session.commit()
    await session.refresh(contest)
    return contest


async def mark_handed_over(
    session: AsyncSession, *, actor_id: uuid.UUID, contest_id: uuid.UUID, user_id: uuid.UUID
) -> ReferralContest:
    """A prize given in person (e.g. a book) was handed over."""
    contest = await get(session, contest_id)
    results = [dict(item) for item in contest.results or []]
    entry = next((item for item in results if item.get("user_id") == str(user_id)), None)
    if entry is None:
        raise NotFoundError("WINNER_NOT_FOUND", "Bu a'zo g'oliblar ro'yxatida yo'q.")
    entry["handed_over"] = True
    contest.results = results
    record_audit(
        session,
        actor_id=actor_id,
        action="CONTEST_PRIZE_HANDED",
        entity_type="referral_contest",
        entity_id=contest.id,
        after={"user_id": str(user_id)},
    )
    await session.commit()
    await session.refresh(contest)
    return contest


# ---------------------------------------------------------------------------- messages


async def _reward_titles(session: AsyncSession, contest: ReferralContest) -> dict[str, str]:
    ids = [uuid.UUID(str(prize["reward_id"])) for prize in contest.prizes or [] if prize.get("reward_id")]
    if not ids:
        return {}
    return {str(reward.id): reward.title for reward in await session.scalars(select(Reward).where(Reward.id.in_(ids)))}


async def _prizes_lines(session: AsyncSession, contest: ReferralContest) -> str:
    titles = await _reward_titles(session, contest)
    lines = [
        f"{place}-o'rin: {prize_text(_prize_for(contest, place), titles)}"
        for place in range(1, contest.winners_count + 1)
        if _prize_for(contest, place)
    ]
    if contest.participation_points:
        lines.append(f"Shartni bajargan har kimga: +{contest.participation_points} ball")
    return "\n".join(lines)


def _participants(contest: ReferralContest) -> Any:
    return select(User.id).where(*eligible_conditions(contest))


async def _announce_start(session: AsyncSession, contest: ReferralContest) -> None:
    contest.announced_at = _now()
    if not contest.announce:
        return
    parts = [f"🏁 <b>Yangi tanlov: {_e(contest.title)}</b>"]
    if contest.description:
        parts.append(_e(contest.description))
    parts.append(
        f"📅 {format_datetime(contest.ends_at)} gacha klubga eng ko'p do'st olib kelganlar g'olib bo'ladi.\n"
        f"✅ Hisoblanadi: {rule_text(contest)}"
        + (f" (kamida {contest.min_friends} ta)" if contest.min_friends > 1 else "")
        + "."
    )
    if contest.show_prizes:
        prizes = await _prizes_lines(session, contest)
        if prizes:
            parts.append(f"🎁 Sovrinlar:\n{prizes}")
    parts.append("👥 Shaxsiy havolangizni ilovadagi «Do'stlar» bo'limidan oling va do'stlaringizga yuboring!")
    await enqueue_for_members(
        session,
        type_=NotificationType.ANNOUNCEMENT,
        text="\n\n".join(parts),
        dedup_prefix=f"contest:{contest.id}:start",
        members=_participants(contest),
        payload=app_button(ROUTE, "👥 Do'stlarni taklif qilish"),
        priority=4,
    )


async def _remind(session: AsyncSession, contest: ReferralContest) -> None:
    contest.reminded_at = _now()
    leaders = await standings(session, contest)
    for row in leaders:
        if row.friends < contest.min_friends:
            need = contest.min_friends - row.friends
            line = f"Sovrin uchun yana {need} ta do'st kerak."
        elif row.place <= contest.winners_count:
            line = f"Hozir siz {row.place}-o'rindasiz — o'rningizni saqlab qoling!"
        else:
            line = f"Hozir siz {row.place}-o'rindasiz — g'oliblarga yetib olish mumkin!"
        await enqueue_notification(
            session,
            user_id=row.user_id,
            type_=NotificationType.ANNOUNCEMENT,
            text=(
                f"⏳ «{_e(contest.title)}» tanlovi {format_datetime(contest.ends_at)} da tugaydi.\n"
                f"Sizning do'stlaringiz: <b>{row.friends}</b>. {line}"
            ),
            dedup_key=f"contest:{contest.id}:remind:{row.user_id}",
            payload=app_button(ROUTE, "👥 Do'stlarni taklif qilish"),
            priority=4,
        )


async def _give(
    session: AsyncSession, contest: ReferralContest, user_id: uuid.UUID, prize: dict[str, Any], key: str, label: str
) -> dict[str, Any]:
    """Give one prize. A refusal (e.g. no promo codes left) is recorded and never stops the others;
    every part is idempotent or checked before anything is written."""
    from app.services import premium as premium_service
    from app.services import rewards as reward_service
    from app.services.scoring import award_points

    given: dict[str, Any] = {}
    errors: list[str] = []
    note = f"🏁 {contest.title} — {label}"
    if prize.get("points"):
        await award_points(
            session,
            user_id=user_id,
            amount=int(prize["points"]),
            category=ScoreCategory.CAMPAIGN,
            idempotency_key=f"contest:{contest.id}:{key}:{user_id}",
            source_type="REFERRAL_CONTEST",
            source_id=contest.id,
            reason=f"«{contest.title}» — {label}",
        )
        given["points"] = int(prize["points"])
    if prize.get("premium_days"):
        if await premium_service.is_lifetime(session, user_id):
            given["premium_days"] = 0  # already has Premium for life
        else:
            await premium_service._extend(
                session,
                user_id=user_id,
                days=int(prize["premium_days"]),
                source=PremiumSource.GIVEAWAY,
                granted_by=contest.created_by,
                note=note,
            )
            given["premium_days"] = int(prize["premium_days"])
    await session.commit()
    if prize.get("reward_id"):
        try:
            await reward_service.assign(
                session,
                actor_id=contest.created_by,  # type: ignore[arg-type]
                reward_id=uuid.UUID(str(prize["reward_id"])),
                user_id=user_id,
                note=note,
                idempotency_key=f"contest:{contest.id}:reward:{user_id}",
                allow_repeat=True,
                message=f"🏁 «{contest.title}» tanlovi sovg'asi! Kodni «🎁 Sovg'alarim» bo'limida ko'rasiz.",
            )
            given["reward_id"] = str(prize["reward_id"])
        except AppError as error:  # raised before anything is written
            errors.append(error.message)
            logger.warning("Contest prize code failed: %s", error.message)
    if errors:
        given["error"] = "; ".join(errors)
    return given


async def finish(session: AsyncSession, *, contest_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> ReferralContest:
    """Choose the winners, give the prizes and tell everybody.

    The final table is saved (and the contest closed) before any prize is given, so a contest is
    never finished twice; each winner's prizes are then recorded as they are given."""
    contest = await get(session, contest_id)
    if contest.status != ContestStatus.PUBLISHED:
        raise ConflictError("CONTEST_NOT_RUNNING", "Faqat e'lon qilingan tanlovni yakunlash mumkin.")
    now = _now()
    if contest.ends_at > now:
        contest.ends_at = now  # finished early by an administrator: the table counts until now
    if contest.starts_at > now:
        contest.starts_at = now
    table = await standings(session, contest)
    results: list[dict[str, Any]] = []
    for row in table:
        if row.friends < contest.min_friends:
            break
        prize = _prize_for(contest, row.place) if row.place <= contest.winners_count else None
        results.append(
            {
                "place": row.place,
                "user_id": str(row.user_id),
                "name": f"{row.last_name} {row.first_name}",
                "friends": row.friends,
                "winner": prize is not None,
                "prize": prize,
                "handed_over": not (prize and prize.get("text")),
            }
        )
    contest.results = results
    contest.status = ContestStatus.FINISHED
    contest.finished_at = now
    record_audit(
        session,
        actor_id=actor_id,
        action="CONTEST_FINISH",
        entity_type="referral_contest",
        entity_id=contest.id,
        after={"winners": [item["user_id"] for item in results if item["winner"]], "participants": len(results)},
    )
    await session.commit()

    titles = await _reward_titles(session, contest)
    for index, entry in enumerate(results):
        user_id = uuid.UUID(entry["user_id"])
        prize = entry["prize"]
        if prize:
            entry["given"] = await _give(session, contest, user_id, prize, "place", f"{entry['place']}-o'rin")
            text = (
                f"🏆 <b>Tabriklaymiz!</b> «{_e(contest.title)}» tanlovida <b>{entry['place']}-o'rin</b> "
                f"({entry['friends']} ta do'st)!\n🎁 Sovg'angiz: {_e(prize_text(prize, titles))}"
            )
            if prize.get("text"):
                text += "\n\nSovg'ani topshirish haqida klub rahbariyati siz bilan bog'lanadi."
            await enqueue_notification(
                session,
                user_id=user_id,
                type_=NotificationType.REWARD,
                text=text,
                dedup_key=f"contest:{contest.id}:win:{user_id}",
                payload=celebrate(app_button(ROUTE, "👥 Natijalar")),
                priority=2,
            )
        if contest.participation_points:
            entry["participation"] = await _give(
                session, contest, user_id, {"points": contest.participation_points}, "join", "ishtirok"
            )
            if not prize:
                await enqueue_notification(
                    session,
                    user_id=user_id,
                    type_=NotificationType.REWARD,
                    text=(
                        f"🙌 «{_e(contest.title)}» tanlovida {entry['friends']} ta do'stni olib keldingiz — "
                        f"rahmat! Sizga +{contest.participation_points} ball."
                    ),
                    dedup_key=f"contest:{contest.id}:thanks:{user_id}",
                    payload=app_button(ROUTE, "👥 Natijalar"),
                    priority=4,
                )
        results[index] = entry
        contest.results = [dict(item) for item in results]  # a new list: the JSON column is saved
        await session.commit()
    await _announce_results(session, contest, results)
    await session.commit()
    await session.refresh(contest)
    return contest


async def _announce_results(session: AsyncSession, contest: ReferralContest, results: list[dict[str, Any]]) -> None:
    winners = [item for item in results if item["winner"]]
    if not winners:
        return
    users = {
        user.id: user
        for user in await session.scalars(select(User).where(User.id.in_([uuid.UUID(w["user_id"]) for w in winners])))
    }
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = []
    for item in winners:
        user = users.get(uuid.UUID(item["user_id"]))
        if user is None:
            continue
        name = _e(name_of(user.first_name, user.last_name, contest.name_format))
        lines.append(f"{medals.get(item['place'], str(item['place']) + '.')} {name} — {item['friends']} ta do'st")
    text = (
        f"🏁 <b>«{_e(contest.title)}» tanlovi yakunlandi!</b>\n\n"
        + "\n".join(lines)
        + "\n\nG'oliblarni tabriklaymiz! Klubga yangi kitobxonlarni olib kelgan hammaga rahmat 📚"
    )
    if contest.announce_results:
        await enqueue_for_members(
            session,
            type_=NotificationType.ANNOUNCEMENT,
            text=text,
            dedup_prefix=f"contest:{contest.id}:results",
            payload=app_button(ROUTE, "👥 Natijalar"),
            priority=4,
        )
    if contest.post_to_channel:
        from app.services import channel

        await channel.queue(session, kind=ChannelPostKind.RESULTS, text=text, dedup_key=f"contest:{contest.id}:results")


async def run_due(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: start announcements, reminders before the end and finishing. Returns the steps done."""
    now = now or _now()
    done = 0
    contests = list(
        await session.scalars(
            select(ReferralContest).where(
                ReferralContest.status == ContestStatus.PUBLISHED, ReferralContest.starts_at <= now
            )
        )
    )
    for contest in contests:
        if contest.ends_at <= now:
            await finish(session, contest_id=contest.id)
            done += 1
            continue
        if contest.announced_at is None:
            await _announce_start(session, contest)
            done += 1
        if (
            contest.remind_hours
            and contest.reminded_at is None
            and now >= contest.ends_at - timedelta(hours=contest.remind_hours)
            and now - contest.starts_at > timedelta(hours=contest.remind_hours)  # not right after the start
        ):
            await _remind(session, contest)
            done += 1
        await session.commit()
    return done


# ---------------------------------------------------------------------------- the members' page


def _visible_name(row: Standing, viewer: User, contest: ReferralContest) -> str:
    if row.user_id == viewer.id:
        return "Siz"
    if contest.name_format == "HIDDEN":
        return "Ishtirokchi"
    return name_of(row.first_name, row.last_name, contest.name_format)


async def member_view(session: AsyncSession, contest: ReferralContest, viewer: User) -> dict[str, Any]:
    """One contest as a member sees it (only what the administrator allowed)."""
    now = _now()
    is_running = running(contest, now)
    table = await standings(session, contest) if contest.status != ContestStatus.FINISHED else []
    mine = next((row for row in table if row.user_id == viewer.id), None)
    eligible = bool(await session.scalar(select(User.id).where(User.id == viewer.id, *eligible_conditions(contest))))
    hidden = frozen(contest, now) and is_running
    leaderboard: list[dict[str, Any]] = []
    if contest.status == ContestStatus.FINISHED:
        users = {
            user.id: user
            for user in await session.scalars(
                select(User).where(User.id.in_([uuid.UUID(item["user_id"]) for item in contest.results or []]))
            )
        }
        for item in (contest.results or [])[: max(contest.leaderboard_size, contest.winners_count)]:
            user = users.get(uuid.UUID(item["user_id"]))
            if user is None:
                continue
            name = "Siz" if user.id == viewer.id else name_of(user.first_name, user.last_name, contest.name_format)
            leaderboard.append(
                {
                    "place": item["place"],
                    "name": name,
                    "friends": item["friends"],
                    "winner": item["winner"],
                    "me": user.id == viewer.id,
                }
            )
        mine_result = next((item for item in contest.results or [] if item["user_id"] == str(viewer.id)), None)
        my_place = mine_result["place"] if mine_result else None
        my_friends = mine_result["friends"] if mine_result else 0
    else:
        if contest.show_leaderboard and not hidden:
            leaderboard = [
                {
                    "place": row.place,
                    "name": _visible_name(row, viewer, contest),
                    "friends": row.friends if contest.show_counts else None,
                    "winner": row.place <= contest.winners_count and row.friends >= contest.min_friends,
                    "me": row.user_id == viewer.id,
                }
                for row in table[: contest.leaderboard_size]
            ]
        my_place = mine.place if mine and contest.show_my_place and not hidden else None
        my_friends = mine.friends if mine else 0
    titles = await _reward_titles(session, contest)
    return {
        "id": contest.id,
        "title": contest.title,
        "description": contest.description,
        "starts_at": contest.starts_at,
        "ends_at": contest.ends_at,
        "state": ("finished" if contest.status == ContestStatus.FINISHED else "running" if is_running else "upcoming"),
        "rule": rule_text(contest),
        "min_friends": contest.min_friends,
        "winners_count": contest.winners_count,
        "prizes": (
            [
                {"place": place, "text": prize_text(_prize_for(contest, place), titles)}
                for place in range(1, contest.winners_count + 1)
                if _prize_for(contest, place)
            ]
            if contest.show_prizes
            else []
        ),
        "participation_points": contest.participation_points if contest.show_prizes else 0,
        "eligible": eligible,
        "leaderboard": leaderboard,
        "leaderboard_hidden": hidden or (not contest.show_leaderboard and contest.status != ContestStatus.FINISHED),
        "show_counts": contest.show_counts or contest.status == ContestStatus.FINISHED,
        "my_friends": my_friends,
        "my_place": my_place,
        "participants": len(table) if contest.status != ContestStatus.FINISHED else len(contest.results or []),
    }


async def for_member(session: AsyncSession, viewer: User) -> list[dict[str, Any]]:
    """Running and upcoming contests, then the ones that finished recently."""
    now = _now()
    contests = list(
        await session.scalars(
            select(ReferralContest)
            .where(
                (ReferralContest.status == ContestStatus.PUBLISHED)
                | (
                    (ReferralContest.status == ContestStatus.FINISHED)
                    & (ReferralContest.finished_at >= now - RECENT_RESULTS)
                )
            )
            .order_by(ReferralContest.status.desc(), ReferralContest.ends_at)
        )
    )
    return [await member_view(session, contest, viewer) for contest in contests]


async def running_line(session: AsyncSession, viewer: User) -> str | None:
    """One line for the bot: the contest that runs now and the member's count."""
    now = _now()
    contest = await session.scalar(
        select(ReferralContest)
        .where(
            ReferralContest.status == ContestStatus.PUBLISHED,
            ReferralContest.starts_at <= now,
            ReferralContest.ends_at > now,
        )
        .order_by(ReferralContest.ends_at)
        .limit(1)
    )
    if contest is None:
        return None
    view = await member_view(session, contest, viewer)
    place = f", {view['my_place']}-o'rin" if view["my_place"] else ""
    return (
        f"🏁 <b>{_e(contest.title)}</b> — {format_datetime(contest.ends_at)} gacha.\n"
        f"Sizda: <b>{view['my_friends']}</b> ta do'st{place}."
    )


async def top_inviters(session: AsyncSession, *, rule: str, limit: int = 100) -> list[dict[str, Any]]:
    """The administrators' all-time view: who brought the most friends (and how many of them came)."""
    from app.services.referrals import came_to_event

    friend = User.__table__.alias("friend")
    rows = await session.execute(
        select(
            User.id,
            User.first_name,
            User.last_name,
            User.group_name,
            Faculty.name,
            func.count(friend.c.id).label("registered"),
            func.count(friend.c.id).filter(came_to_event(friend.c.id)).label("attended"),
        )
        .join(friend, friend.c.referred_by == User.id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .where(friend.c.deleted_at.is_(None), friend.c.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
        .group_by(User.id, Faculty.name)
        .order_by(
            (
                func.count(friend.c.id).filter(came_to_event(friend.c.id))
                if rule == "ATTENDED"
                else func.count(friend.c.id)
            ).desc(),
            func.count(friend.c.id).desc(),
        )
        .limit(limit)
    )
    return [
        {
            "place": place,
            "user_id": row[0],
            "name": f"{row[2]} {row[1]}",
            "group_name": row[3],
            "faculty": row[4],
            "registered": int(row[5]),
            "attended": int(row[6]),
        }
        for place, row in enumerate(rows, start=1)
    ]
