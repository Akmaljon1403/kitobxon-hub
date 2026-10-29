"""«🎯 Shaxsiy missiyalar»: small personal goals set by the admins («7 kunda 100 bet», «5 kun ketma-ket
o'qish», «2 haftada 2 ta tadbir») that a member takes on in the Mini App — and goals a member sets for
themself («🎯 O'z missiyam»), seen only by them (and by the admins in the panel).

A taken mission has its own window: from the moment it is taken, ``period_days`` long. Progress is
always counted from what the member really did in that window (the reading diary, the shelf, verified
attendance, submitted tests, saved quotes, «3 savol»), never typed in. When the target is reached the
member gets the points once and a celebrating message; a mission that runs out can be taken again.
"""

from __future__ import annotations

import html
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    AttendanceRecord,
    BookReflection,
    Mission,
    ReadingLog,
    SavedQuote,
    ShelfItem,
    TestAttempt,
    User,
    UserMission,
)
from app.models.enums import (
    AttemptStatus,
    AttendanceStatus,
    MissionMetric,
    MissionStatus,
    NotificationType,
    ScoreCategory,
    ShelfStatus,
    UserMissionStatus,
)
from app.services.audit import record_audit
from app.utils.timezone import local_tz

MAX_ACTIVE = 5
MAX_PERSONAL = 10  # a member's own missions kept at once
PERSONAL_DAYS = (1, 90)
REFRESH_EVERY = timedelta(minutes=30)
BATCH = 200

# (unit for "12 / 100 bet", the short phrase for the admins' list)
METRICS: dict[MissionMetric, tuple[str, str]] = {
    MissionMetric.PAGES: ("bet", "mutolaa kundaligidagi betlar"),
    MissionMetric.READING_DAYS: ("kun", "kitob o'qilgan kunlar"),
    MissionMetric.STREAK: ("kun ketma-ket", "ketma-ket o'qilgan kunlar"),
    MissionMetric.BOOKS_FINISHED: ("kitob", "o'qib tugatilgan kitoblar"),
    MissionMetric.EVENTS: ("tadbir", "tasdiqlangan tadbir davomati"),
    MissionMetric.TESTS: ("test", "topshirilgan testlar"),
    MissionMetric.QUOTES: ("iqtibos", "saqlangan iqtiboslar"),
    MissionMetric.REFLECTIONS: ("javob", "«3 savol»ga javoblar"),
}


# A member's own mission: (smallest, largest) target, and the smallest target that earns points — so that
# «1 bet in 7 days» is still a fine goal for oneself, but not a way to collect points.
PERSONAL_TARGETS: dict[MissionMetric, tuple[int, int, int]] = {
    MissionMetric.PAGES: (5, 5000, 50),
    MissionMetric.READING_DAYS: (1, 90, 3),
    MissionMetric.STREAK: (2, 90, 3),
    MissionMetric.BOOKS_FINISHED: (1, 30, 1),
    MissionMetric.EVENTS: (1, 20, 1),
    MissionMetric.TESTS: (1, 20, 1),
    MissionMetric.QUOTES: (1, 200, 3),
    MissionMetric.REFLECTIONS: (1, 20, 1),
}
PERSONAL_ICONS = ("🎯", "📖", "🔥", "📚", "💬", "💡", "📅", "🧠", "🏃", "⭐", "🌱", "🏆")


# Ready-made missions, so members find something to take on the first day (admins edit or archive them).
DEFAULTS: tuple[dict[str, Any], ...] = (
    {
        "title": "7 kunda 100 bet",
        "description": "Bir hafta ichida mutolaa kundaligiga jami 100 bet yozing.",
        "icon": "📖",
        "metric": MissionMetric.PAGES,
        "target": 100,
        "period_days": 7,
        "reward_points": 15,
    },
    {
        "title": "5 kun ketma-ket o'qish",
        "description": "Besh kun uzluksiz — har kuni ozgina bo'lsa ham o'qing va kundalikka yozing.",
        "icon": "🔥",
        "metric": MissionMetric.STREAK,
        "target": 5,
        "period_days": 7,
        "reward_points": 10,
    },
    {
        "title": "Bir oyda 2 ta kitob",
        "description": "30 kun ichida javoningizdagi 2 ta kitobni o'qib tugating.",
        "icon": "📚",
        "metric": MissionMetric.BOOKS_FINISHED,
        "target": 2,
        "period_days": 30,
        "reward_points": 25,
    },
    {
        "title": "5 ta iqtibos saqlang",
        "description": "Ikki hafta ichida «📚 Javonim»da yoqqan 5 ta iqtibosni saqlang.",
        "icon": "💬",
        "metric": MissionMetric.QUOTES,
        "target": 5,
        "period_days": 14,
        "reward_points": 5,
    },
    {
        "title": "Kitobdan keyin 3 savol",
        "description": "O'qib tugatgan kitobingiz haqida 3 ta savolga javob yozing.",
        "icon": "💡",
        "metric": MissionMetric.REFLECTIONS,
        "target": 1,
        "period_days": 30,
        "reward_points": 5,
    },
    {
        "title": "2 haftada 2 ta tadbir",
        "description": "Ikki hafta ichida klubning 2 ta tadbirida qatnashing.",
        "icon": "📅",
        "metric": MissionMetric.EVENTS,
        "target": 2,
        "period_days": 14,
        "reward_points": 10,
    },
)


async def seed_defaults(session: AsyncSession) -> int:
    """The ready-made missions, once: only while the club has no missions at all (the caller commits)."""
    # The web process and the worker start together: only one of them seeds.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext("missions:seed"))))
    if await session.scalar(select(func.count()).select_from(Mission).where(Mission.owner_id.is_(None))):
        return 0
    session.add_all(Mission(**values) for values in DEFAULTS)
    return len(DEFAULTS)


def _local_day(moment: datetime) -> date:
    return moment.astimezone(local_tz()).date()


async def count(
    session: AsyncSession, user_id: uuid.UUID, metric: MissionMetric, start: datetime, end: datetime
) -> int:
    """What the member did between ``start`` and ``end`` for this metric."""
    from app.services.reading_journal import streaks

    first, last = _local_day(start), _local_day(end)
    if metric in (MissionMetric.PAGES, MissionMetric.READING_DAYS, MissionMetric.STREAK):
        window = (
            ReadingLog.user_id == user_id,
            ReadingLog.log_date >= first,
            ReadingLog.log_date <= last,
            ReadingLog.created_at >= start,  # written after taking the mission
        )
        if metric == MissionMetric.PAGES:
            return int(await session.scalar(select(func.coalesce(func.sum(ReadingLog.pages), 0)).where(*window)) or 0)
        days = list(await session.scalars(select(ReadingLog.log_date).where(*window).distinct()))
        if metric == MissionMetric.READING_DAYS:
            return len(days)
        return streaks(days, last)[1]
    if metric == MissionMetric.BOOKS_FINISHED:
        # A club book, or a book of one's own that the diary shows was really read.
        read_in_diary = exists().where(ReadingLog.shelf_item_id == ShelfItem.id)
        query = (
            select(func.count())
            .select_from(ShelfItem)
            .where(
                ShelfItem.user_id == user_id,
                ShelfItem.status == ShelfStatus.FINISHED,
                ShelfItem.finished_at >= start,
                ShelfItem.finished_at <= end,
                or_(ShelfItem.book_id.is_not(None), read_in_diary),
            )
        )
    elif metric == MissionMetric.EVENTS:
        query = (
            select(func.count())
            .select_from(AttendanceRecord)
            .where(
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.status == AttendanceStatus.VERIFIED,
                AttendanceRecord.checked_in_at >= start,
                AttendanceRecord.checked_in_at <= end,
            )
        )
    elif metric == MissionMetric.TESTS:
        query = (
            select(func.count())
            .select_from(TestAttempt)
            .where(
                TestAttempt.user_id == user_id,
                TestAttempt.status == AttemptStatus.SUBMITTED,
                TestAttempt.submitted_at >= start,
                TestAttempt.submitted_at <= end,
            )
        )
    elif metric == MissionMetric.QUOTES:
        query = (
            select(func.count())
            .select_from(SavedQuote)
            .where(SavedQuote.user_id == user_id, SavedQuote.created_at >= start, SavedQuote.created_at <= end)
        )
    else:
        query = (
            select(func.count())
            .select_from(BookReflection)
            .where(
                BookReflection.user_id == user_id, BookReflection.created_at >= start, BookReflection.created_at <= end
            )
        )
    return int(await session.scalar(query) or 0)


def describe(mission: Mission, mine: UserMission | None) -> dict[str, Any]:
    unit, _ = METRICS[mission.metric]
    return {
        "id": mission.id,
        "title": mission.title,
        "description": mission.description,
        "icon": mission.icon,
        "metric": mission.metric,
        "unit": unit,
        "target": mission.target,
        "period_days": mission.period_days,
        "reward_points": mission.reward_points,
        "status": mine.status if mine else None,
        "progress": min(mine.progress, mission.target) if mine else 0,
        "started_at": mine.started_at if mine else None,
        "deadline": mine.deadline if mine else None,
        "completed_at": mine.completed_at if mine else None,
        "attempts": mine.attempts if mine else 0,
        "personal": mission.owner_id is not None,
    }


async def for_member(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    """Active missions with the member's own progress (taken ones first), refreshed now."""
    await refresh(session, user.id)
    missions = list(
        await session.scalars(
            select(Mission)
            .where(
                Mission.status == MissionStatus.ACTIVE,
                or_(Mission.owner_id.is_(None), Mission.owner_id == user.id),
            )
            .order_by(Mission.created_at)
        )
    )
    mine = {
        row.mission_id: row for row in await session.scalars(select(UserMission).where(UserMission.user_id == user.id))
    }
    order = {UserMissionStatus.ACTIVE: 0, None: 1, UserMissionStatus.EXPIRED: 2, UserMissionStatus.COMPLETED: 3}
    items = [describe(mission, mine.get(mission.id)) for mission in missions]
    items.sort(key=lambda item: order.get(item["status"], 1))
    return items


async def take(session: AsyncSession, user: User, mission_id: uuid.UUID) -> UserMission:
    """Start a mission now (again, if the last try ran out)."""
    mission = await session.get(Mission, mission_id)
    if mission is None or mission.status != MissionStatus.ACTIVE or mission.owner_id not in (None, user.id):
        raise NotFoundError("MISSION_NOT_FOUND", "Bu missiya hozir ochiq emas.")
    active = await session.scalar(
        select(func.count())
        .select_from(UserMission)
        .where(UserMission.user_id == user.id, UserMission.status == UserMissionStatus.ACTIVE)
    )
    if (active or 0) >= MAX_ACTIVE:
        raise ConflictError("TOO_MANY_MISSIONS", f"Bir vaqtda {MAX_ACTIVE} tagacha missiya olish mumkin.")
    now = datetime.now(UTC)
    deadline = now + timedelta(days=mission.period_days)
    mine = await session.scalar(
        select(UserMission).where(UserMission.mission_id == mission.id, UserMission.user_id == user.id)
    )
    if mine is None:
        mine = UserMission(mission_id=mission.id, user_id=user.id, started_at=now, deadline=deadline)
        session.add(mine)
    elif mine.status == UserMissionStatus.COMPLETED:
        raise ConflictError("MISSION_DONE", "Bu missiyani allaqachon bajargansiz. 🎉")
    elif mine.status == UserMissionStatus.ACTIVE:
        raise ConflictError("MISSION_ACTIVE", "Bu missiya allaqachon davom etmoqda.")
    else:
        mine.status = UserMissionStatus.ACTIVE
        mine.started_at, mine.deadline, mine.progress = now, deadline, 0
        mine.attempts += 1
    await session.commit()
    await session.refresh(mine)
    return mine


async def give_up(session: AsyncSession, user: User, mission_id: uuid.UUID) -> None:
    mine = await session.scalar(
        select(UserMission).where(
            UserMission.mission_id == mission_id,
            UserMission.user_id == user.id,
            UserMission.status == UserMissionStatus.ACTIVE,
        )
    )
    if mine is None:
        raise NotFoundError("MISSION_NOT_TAKEN", "Bu missiya olinmagan.")
    mine.status = UserMissionStatus.EXPIRED
    await session.commit()


async def _finish(session: AsyncSession, mine: UserMission, mission: Mission) -> None:
    from app.services.notifications import celebrate, enqueue_notification, render
    from app.services.scoring import award_points

    mine.status = UserMissionStatus.COMPLETED
    mine.completed_at = datetime.now(UTC)
    points = mission.reward_points
    capped = False
    if mission.owner_id is not None and points:
        points, capped = await _personal_reward(session, mine, mission)
    if points:
        await award_points(
            session,
            user_id=mine.user_id,
            amount=points,
            category=ScoreCategory.CAMPAIGN,
            idempotency_key=f"mission:{mine.id}:{mine.attempts}",
            source_type="MISSION",
            source_id=mission.id,
            reason=f"Missiya bajarildi: {mission.title}"[:250],
        )
    reward = f" Sizga <b>+{points} ball</b>." if points else ""
    if capped:
        reward = " Bu oy shaxsiy missiyalar uchun ball chegarasiga yetdingiz — g'alaba baribir sizniki!"
    tail = "O'zingizga yangi maqsad qo'ying 🎯" if mission.owner_id else "Yangi missiyalar kutmoqda 🎯"
    message = f"{mission.icon} <b>Missiya bajarildi: {html.escape(mission.title)}!</b>{reward} {tail}"
    await enqueue_notification(
        session,
        user_id=mine.user_id,
        type_=NotificationType.SYSTEM,
        text=await render(session, NotificationType.SYSTEM, message=message) or message,
        dedup_key=f"mission-done:{mine.id}:{mine.attempts}",
        payload=celebrate({"buttons": [{"text": "🎯 Missiyalarim", "app_route": "missions"}]}),
        priority=3,
    )


async def _personal_reward(session: AsyncSession, mine: UserMission, mission: Mission) -> tuple[int, bool]:
    """(points, capped) for finishing one's own mission: nothing for a very easy goal, and only so many
    a month (``missions.personal_monthly_limit``)."""
    from app.models import ScoreTransaction
    from app.services.settings import get_setting

    _, _, earns_from = PERSONAL_TARGETS[mission.metric]
    if mission.target < earns_from:
        return 0, False
    limit = int(await get_setting(session, "missions.personal_monthly_limit"))
    if limit:
        month_start = datetime.now(local_tz()).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        earned = await session.scalar(
            select(func.count())
            .select_from(ScoreTransaction)
            .join(Mission, Mission.id == ScoreTransaction.source_id)
            .where(
                ScoreTransaction.user_id == mine.user_id,
                ScoreTransaction.source_type == "MISSION",
                ScoreTransaction.created_at >= month_start,
                Mission.owner_id.is_not(None),
            )
        )
        if (earned or 0) >= limit:
            return 0, True
    return mission.reward_points, False


async def refresh(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Count the member's running missions again; finish or close them. Returns how many finished now."""
    rows = (
        await session.execute(
            select(UserMission, Mission)
            .join(Mission, Mission.id == UserMission.mission_id)
            .where(UserMission.user_id == user_id, UserMission.status == UserMissionStatus.ACTIVE)
        )
    ).all()
    if not rows:
        return 0
    now = datetime.now(UTC)
    finished = 0
    for mine, mission in rows:
        mine.progress = await count(session, user_id, mission.metric, mine.started_at, min(now, mine.deadline))
        mine.updated_at = now
        if mine.progress >= mission.target:
            await _finish(session, mine, mission)
            finished += 1
        elif now > mine.deadline:
            mine.status = UserMissionStatus.EXPIRED
    await session.commit()
    return finished


async def check_running(session: AsyncSession) -> int:
    """Scheduled: running missions not looked at for a while (attendance and tests happen elsewhere),
    and those whose time is up."""
    now = datetime.now(UTC)
    users = list(
        await session.scalars(
            select(UserMission.user_id)
            .where(
                UserMission.status == UserMissionStatus.ACTIVE,
                (UserMission.updated_at < now - REFRESH_EVERY) | (UserMission.deadline < now),
            )
            .distinct()
            .limit(BATCH)
        )
    )
    done = 0
    for user_id in users:
        done += await refresh(session, user_id)
    return done


# ---------------------------------------------------------------------------- the Admin Panel


async def admin_list(session: AsyncSession) -> list[dict[str, Any]]:
    missions = list(
        await session.scalars(
            select(Mission).where(Mission.owner_id.is_(None)).order_by(Mission.status, Mission.created_at)
        )
    )
    stats = {
        mission_id: (int(taken), int(done), int(running))
        for mission_id, taken, done, running in (
            await session.execute(
                select(
                    UserMission.mission_id,
                    func.count(),
                    func.count().filter(UserMission.status == UserMissionStatus.COMPLETED),
                    func.count().filter(UserMission.status == UserMissionStatus.ACTIVE),
                ).group_by(UserMission.mission_id)
            )
        ).all()
    }
    result = []
    for mission in missions:
        taken, done, running = stats.get(mission.id, (0, 0, 0))
        result.append(
            {
                **describe(mission, None),
                "status": mission.status,
                "taken": taken,
                "completed": done,
                "running": running,
                "completion_rate": round(done * 100 / taken) if taken else None,
                "metric_title": METRICS[mission.metric][1],
            }
        )
    return result


_FIELDS = ("title", "description", "icon", "metric", "target", "period_days", "reward_points", "status")


async def save(
    session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any], mission_id: uuid.UUID | None = None
) -> Mission:
    if mission_id is None:
        mission = Mission(created_by=actor_id, **{key: data[key] for key in _FIELDS if key in data})
        session.add(mission)
        action = "MISSION_CREATE"
    else:
        found = await session.get(Mission, mission_id)
        if found is None or found.owner_id is not None:  # a member's own mission is theirs to change
            raise NotFoundError("MISSION_NOT_FOUND", "Missiya topilmadi.")
        mission = found
        taken = await session.scalar(
            select(func.count()).select_from(UserMission).where(UserMission.mission_id == mission.id)
        )
        if taken and any(key in data and data[key] != getattr(mission, key) for key in ("metric", "target")):
            raise BadRequestError(
                "MISSION_TAKEN", "Missiyani a'zolar olgan: shart va maqsadni o'zgartirmang — yangisini yarating."
            )
        for key in _FIELDS:
            if key in data:
                setattr(mission, key, data[key])
        action = "MISSION_UPDATE"
    await session.flush()
    record_audit(session, actor_id=actor_id, action=action, entity_type="mission", entity_id=mission.id, after=data)
    await session.commit()
    await session.refresh(mission)
    return mission


# ---------------------------------------------------------------------------- «🎯 O'z missiyam» (a member's own)


def personal_options() -> list[dict[str, Any]]:
    """What a member can count in their own mission, with the allowed targets."""
    return [
        {
            "code": metric,
            "title": title,
            "unit": unit,
            "min": PERSONAL_TARGETS[metric][0],
            "max": PERSONAL_TARGETS[metric][1],
            "points_from": PERSONAL_TARGETS[metric][2],
        }
        for metric, (unit, title) in METRICS.items()
    ]


async def create_personal(session: AsyncSession, user: User, data: dict[str, Any]) -> Mission:
    """A member's own goal: saved, started at once and counted like any other mission."""
    from app.services.settings import get_setting

    if not await get_setting(session, "missions.personal_enabled"):
        raise ConflictError("PERSONAL_MISSIONS_OFF", "Shaxsiy missiya yaratish hozircha yopiq.")
    metric = MissionMetric(data["metric"])
    low, high, _ = PERSONAL_TARGETS[metric]
    target, days = int(data["target"]), int(data["period_days"])
    if not low <= target <= high:
        unit = METRICS[metric][0]
        raise BadRequestError("TARGET_OUT_OF_RANGE", f"Maqsad {low}–{high} {unit} oralig'ida bo'lishi kerak.")
    if not PERSONAL_DAYS[0] <= days <= PERSONAL_DAYS[1]:
        raise BadRequestError("PERIOD_OUT_OF_RANGE", f"Muddat {PERSONAL_DAYS[0]}–{PERSONAL_DAYS[1]} kun bo'lsin.")
    if metric in (MissionMetric.READING_DAYS, MissionMetric.STREAK) and target > days:
        raise BadRequestError(
            "TARGET_OUT_OF_RANGE", f"{days} kunda {target} kun o'qib bo'lmaydi — muddatni uzaytiring."
        )
    title = " ".join(str(data["title"]).split())
    if len(title) < 3:
        raise BadRequestError("TITLE_TOO_SHORT", "Missiyaga nom bering (kamida 3 harf).")
    kept = await session.scalar(
        select(func.count())
        .select_from(Mission)
        .where(Mission.owner_id == user.id, Mission.status == MissionStatus.ACTIVE)
    )
    if (kept or 0) >= MAX_PERSONAL:
        raise ConflictError(
            "TOO_MANY_PERSONAL",
            f"Shaxsiy missiyalar {MAX_PERSONAL} tadan oshmasin — eskisini o'chirib, yangisini qo'shing.",
        )
    icon = data.get("icon") if data.get("icon") in PERSONAL_ICONS else "🎯"
    description = " ".join(str(data.get("description") or "").split()) or None
    mission = Mission(
        title=title[:80],
        description=description[:300] if description else None,
        icon=icon,
        metric=metric,
        target=target,
        period_days=days,
        reward_points=int(await get_setting(session, "missions.personal_points")),
        status=MissionStatus.ACTIVE,
        owner_id=user.id,
        created_by=user.id,
    )
    session.add(mission)
    await session.flush()
    await take(session, user, mission.id)
    return mission


async def delete_personal(session: AsyncSession, user: User, mission_id: uuid.UUID) -> None:
    mission = await session.get(Mission, mission_id)
    if mission is None or mission.owner_id != user.id:
        raise NotFoundError("MISSION_NOT_FOUND", "Missiya topilmadi.")
    await session.delete(mission)
    await session.commit()


async def personal_overview(session: AsyncSession, limit: int = 100) -> dict[str, Any]:
    """For the admins: what members set for themselves — the totals and the latest ones."""
    totals = (
        await session.execute(
            select(
                func.count(Mission.id),
                func.count(func.distinct(Mission.owner_id)),
                func.count(UserMission.id).filter(UserMission.status == UserMissionStatus.ACTIVE),
                func.count(UserMission.id).filter(UserMission.status == UserMissionStatus.COMPLETED),
            )
            .select_from(Mission)
            .outerjoin(UserMission, UserMission.mission_id == Mission.id)
            .where(Mission.owner_id.is_not(None))
        )
    ).one()
    rows = (
        await session.execute(
            select(Mission, UserMission, User)
            .join(User, User.id == Mission.owner_id)
            .outerjoin(UserMission, UserMission.mission_id == Mission.id)
            .where(Mission.owner_id.is_not(None))
            .order_by(Mission.created_at.desc())
            .limit(limit)
        )
    ).all()
    popular = (
        await session.execute(
            select(Mission.metric, func.count())
            .where(Mission.owner_id.is_not(None))
            .group_by(Mission.metric)
            .order_by(func.count().desc())
        )
    ).all()
    return {
        "created": int(totals[0]),
        "members": int(totals[1]),
        "running": int(totals[2]),
        "completed": int(totals[3]),
        "popular": [{"metric": metric, "title": METRICS[metric][1], "count": int(n)} for metric, n in popular],
        "items": [
            {
                **describe(mission, mine),
                "owner_id": user.id,
                "owner_name": f"{user.last_name or ''} {user.first_name}".strip(),
                "group_name": user.group_name,
                "created_at": mission.created_at,
            }
            for mission, mine, user in rows
        ],
    }


async def promote_personal(session: AsyncSession, *, actor_id: uuid.UUID, mission_id: uuid.UUID) -> Mission:
    """A good idea from a member becomes a club mission (a draft the admins finish and open for all)."""
    source = await session.get(Mission, mission_id)
    if source is None or source.owner_id is None:
        raise NotFoundError("MISSION_NOT_FOUND", "Missiya topilmadi.")
    return await save(
        session,
        actor_id=actor_id,
        data={
            "title": source.title,
            "description": source.description,
            "icon": source.icon,
            "metric": source.metric,
            "target": source.target,
            "period_days": source.period_days,
            "reward_points": 0,
            "status": MissionStatus.DRAFT,
        },
    )


async def remove_personal(session: AsyncSession, *, actor_id: uuid.UUID, mission_id: uuid.UUID) -> None:
    """The admins remove a member's own mission (an unsuitable name, for instance)."""
    mission = await session.get(Mission, mission_id)
    if mission is None or mission.owner_id is None:
        raise NotFoundError("MISSION_NOT_FOUND", "Missiya topilmadi.")
    record_audit(
        session,
        actor_id=actor_id,
        action="MISSION_PERSONAL_DELETE",
        entity_type="mission",
        entity_id=mission.id,
        before={"title": mission.title, "owner_id": str(mission.owner_id)},
    )
    await session.delete(mission)
    await session.commit()
