"""The club over the years: a new study year, members who stopped coming, and old records.

* **New study year** (1 September by default): every active member moves up one course (up to the
  last course), a season «2026–2027 o'quv yili» starts — rankings and reports of different years
  never mix — and members are told. History (points, books, certificates) stays as it is.
* **Inactive members**: nobody has seen a member (bot or app) for a long time → a friendly
  reminder, and a week later the account becomes «faol emas»: no more messages. Nothing is deleted;
  the member is welcomed back automatically when they return (/start or the app).
* **Old records**: delivered notifications, test signals and stale conversation states are removed
  after a while, so the database stays small and fast after years of use. The audit log is never
  removed (the database itself forbids it).
"""

from __future__ import annotations

import calendar
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import String, delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BotFsmState,
    Notification,
    Role,
    Season,
    TestActivityLog,
    User,
    UserRole,
)
from app.models.enums import NotificationStatus, NotificationType, UserStatus
from app.services.audit import record_audit
from app.services.notifications import enqueue_notification
from app.services.settings import get_setting, update_setting
from app.utils.timezone import local_tz

logger = logging.getLogger(__name__)

INACTIVE_REASON = "inactivity"
WARNING_DAYS = 7
SEEN_EVERY = timedelta(hours=6)  # how often the bot writes «last seen» (not on every message)
NOTIFICATIONS_KEEP_DAYS = 120
SIGNALS_KEEP_DAYS = 400
FSM_KEEP_DAYS = 45
BATCH = 5_000


def _now() -> datetime:
    return datetime.now(UTC)


def _start_date(year: int, month_day: str) -> date:
    month, day = (int(part) for part in month_day.split("-"))
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))  # «02-30» → the last day of February


def study_year_start(today: date, month_day: str = "09-01") -> int:
    """The calendar year in which the current study year began."""
    month, day = (int(part) for part in month_day.split("-"))
    return today.year if (today.month, today.day) >= (month, day) else today.year - 1


# ---------------------------------------------------------------------------- the new study year


async def new_study_year(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job. Returns how many members moved up a course (0 when there is nothing to do)."""
    now = now or _now()
    today = now.astimezone(local_tz()).date()
    start_day = str(await get_setting(session, "academic.year_start"))
    year = study_year_start(today, start_day)
    current = int(await get_setting(session, "academic.current_year"))
    if current == 0:
        # First run after installing: remember the year, change nothing.
        await update_setting(session, key="academic.current_year", value=year, actor_id=None)
        await session.commit()
        return 0
    if current >= year:
        return 0
    # Recorded first: even if something below fails, the courses are never raised twice.
    await update_setting(session, key="academic.current_year", value=year, actor_id=None)
    moved = 0
    max_course = int(await get_setting(session, "registration.max_course"))
    if await get_setting(session, "academic.ask_graduates"):
        await _ask_graduates(session, year, max_course)
    if await get_setting(session, "academic.promote_courses"):
        students = (
            User.deleted_at.is_(None),
            User.status == UserStatus.ACTIVE,
            User.course.is_not(None),
            User.course < max_course,
            User.graduated_at.is_(None),
        )
        if await get_setting(session, "academic.promote_groups"):
            # «201» of a 2nd-year student becomes «301»; groups named otherwise stay as they are.
            await session.execute(
                update(User)
                .where(*students, func.left(User.group_name, 1) == func.cast(User.course, String))
                .values(group_name=func.cast(User.course + 1, String) + func.substr(User.group_name, 2))
            )
        result = await session.execute(
            update(User).where(*students).values(course=User.course + 1).returning(User.id, User.course)
        )
        promoted = result.all()
        moved = len(promoted)
        for user_id, course in promoted:
            await enqueue_notification(
                session,
                user_id=user_id,
                type_=NotificationType.SYSTEM,
                text=(
                    f"🎓 Yangi o'quv yili muborak! Endi siz {course}-kursdasiz. Kurs yoki guruhingiz noto'g'ri "
                    "bo'lsa, ilovada «👤 Profil» → «✏️ O'zgartirish» orqali to'g'rilang."
                ),
                dedup_key=f"study-year:{year}:{user_id}",
                payload={"buttons": [{"text": "👤 Profil", "app_route": "profile"}]},
            )
    record_audit(
        session,
        actor_id=None,
        action="STUDY_YEAR_START",
        entity_type="academic_year",
        entity_id=str(year),
        after={"promoted": moved},
    )
    if await get_setting(session, "academic.auto_season"):
        await _open_season(session, year, start_day)
    await session.commit()
    logger.info("A new study year started: %s, %s members moved up", year, moved)
    return moved


GRADUATE_BUTTONS = [
    {"text": "🎓 Ha, bitirdim", "callback": "grad:yes"},
    {"text": "📚 Hali o'qiyman", "callback": "grad:no"},
]


async def _ask_graduates(session: AsyncSession, year: int, max_course: int) -> int:
    """Members of the last course: «Bitirdingizmi?» with two buttons (see the bot's ``grad:`` buttons)."""
    ids = list(
        await session.scalars(
            select(User.id).where(
                User.deleted_at.is_(None),
                User.status == UserStatus.ACTIVE,
                User.course >= max_course,
                User.graduated_at.is_(None),
            )
        )
    )
    for user_id in ids:
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.SYSTEM,
            text=(
                "🎓 Yangi o'quv yili boshlandi! Siz oxirgi kursda edingiz — o'qishni tamomladingizmi?\n\n"
                "Bitirgan bo'lsangiz, klubda <b>bitiruvchi</b> sifatida qolasiz: ballaringiz, kitoblaringiz va "
                "sertifikatlaringiz joyida, tadbirlarga kelaverasiz 📚"
            ),
            dedup_key=f"graduate-question:{year}:{user_id}",
            payload={"buttons": [{"row": GRADUATE_BUTTONS}]},
            priority=4,
        )
    return len(ids)


async def set_graduated(session: AsyncSession, user: User, graduated: bool) -> None:
    """The member's own answer to «Bitirdingizmi?»."""
    if graduated and user.graduated_at is None:
        user.graduated_at = _now()
        record_audit(session, actor_id=user.id, action="USER_GRADUATED", entity_type="user", entity_id=user.id)
    elif not graduated and user.graduated_at is not None:
        user.graduated_at = None
    await session.commit()


async def _open_season(session: AsyncSession, year: int, month_day: str) -> None:
    from app.services.seasons import activate_season

    name = f"{year}–{year + 1} o'quv yili"
    season = await session.scalar(select(Season).where(Season.name == name))
    if season is None:
        starts_on = _start_date(year, month_day)
        ends_on = _start_date(year + 1, month_day) - timedelta(days=1)
        season = Season(name=name, starts_on=starts_on, ends_on=ends_on)
        session.add(season)
        await session.flush()
    await activate_season(session, actor_id=None, season_id=season.id)


# ---------------------------------------------------------------------------- members who stopped coming


async def touch(session: AsyncSession, user: User) -> bool:
    """The member was seen (in the bot): written at most every few hours. True when changed."""
    now = _now()
    if user.last_seen_at is not None and now - user.last_seen_at < SEEN_EVERY:
        return False
    user.last_seen_at = now
    return True


async def wake_up(session: AsyncSession, user: User) -> bool:
    """A member made inactive automatically comes back by themselves. True when reactivated."""
    if user.status != UserStatus.INACTIVE or user.left_reason != INACTIVE_REASON or user.deleted_at is not None:
        return False
    user.status = UserStatus.ACTIVE
    user.left_reason = None
    user.last_seen_at = _now()
    record_audit(session, actor_id=user.id, action="USER_WAKE_UP", entity_type="user", entity_id=user.id)
    await session.commit()
    return True


def _staff() -> object:
    """Administrators are never made inactive (every member has the USER role; admins have more)."""
    from app.services.rbac import ADMIN_ROLES

    return exists().where(UserRole.user_id == User.id, UserRole.role_id == Role.id, Role.code.in_(ADMIN_ROLES))


async def inactive_members(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: remind members not seen for a long time, then mark them «faol emas».
    Returns how many became inactive."""
    days = int(await get_setting(session, "membership.inactive_days"))
    if days <= 0:
        return 0
    now = now or _now()
    last_seen = func.coalesce(User.last_seen_at, User.registered_at, User.created_at)
    base = [User.deleted_at.is_(None), User.status == UserStatus.ACTIVE, ~_staff()]
    warn_before = now - timedelta(days=max(days - WARNING_DAYS, 1))

    def warning(*conditions: object) -> object:
        # A warning sent after the member was last seen (one from an earlier break does not count).
        return exists().where(
            Notification.user_id == User.id,
            Notification.dedup_key.like("inactive-warning:%"),
            Notification.created_at >= last_seen,
            *conditions,
        )

    to_warn = list(
        await session.scalars(select(User.id).where(*base, last_seen < warn_before, ~warning()).limit(BATCH))
    )
    for user_id in to_warn:
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.SYSTEM,
            text=(
                "👋 Sizni ancha vaqtdan beri ko'rmadik! Klubda yangi kitoblar, tadbirlar va testlar kutmoqda. "
                f"{WARNING_DAYS} kun ichida botga yoki ilovaga kirmasangiz, hisobingiz «faol emas» bo'ladi va "
                "xabarlar to'xtaydi. Qaytganingizda hammasi joyida bo'ladi — ballaringiz ham."
            ),
            dedup_key=f"inactive-warning:{user_id}:{now.astimezone(local_tz()):%Y-%m}",
            payload={"buttons": [{"text": "✋ Men shu yerdaman", "callback": "mem:alive"}]},
            priority=2,
        )
    warned = warning(Notification.created_at <= now - timedelta(days=WARNING_DAYS))  # a week to come back
    stale = list(
        await session.scalars(select(User).where(*base, last_seen < now - timedelta(days=days), warned).limit(BATCH))
    )
    for user in stale:
        user.status = UserStatus.INACTIVE
        user.left_reason = INACTIVE_REASON
        user.token_version += 1
        record_audit(
            session,
            actor_id=None,
            action="USER_AUTO_INACTIVE",
            entity_type="user",
            entity_id=user.id,
            reason=f"{days} kundan beri faol emas",
        )
    await session.commit()
    return len(stale)


# ---------------------------------------------------------------------------- old records


async def cleanup(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: remove records nobody needs any more (in batches). Returns how many rows went."""
    now = now or _now()
    removed = 0

    async def chunk(table: type, *conditions: object) -> int:
        ids = select(table.id).where(*conditions).limit(BATCH).scalar_subquery()  # type: ignore[attr-defined]
        result = await session.execute(delete(table).where(table.id.in_(ids)))  # type: ignore[attr-defined]
        return int(result.rowcount or 0)

    removed += await chunk(
        Notification,
        Notification.status != NotificationStatus.PENDING,
        Notification.created_at < now - timedelta(days=NOTIFICATIONS_KEEP_DAYS),
    )
    removed += await chunk(TestActivityLog, TestActivityLog.created_at < now - timedelta(days=SIGNALS_KEEP_DAYS))
    result = await session.execute(
        delete(BotFsmState).where(BotFsmState.updated_at < now - timedelta(days=FSM_KEEP_DAYS))
    )
    removed += int(result.rowcount or 0)
    await session.commit()
    if removed:
        logger.info("Old records removed: %s", removed)
    return removed


# ---------------------------------------------------------------------------- «Yil yakuni»


async def year_summaries(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job (daily): on ``academic.summary_day`` every member who did something this study year
    gets their own results. Returns how many messages were queued."""
    from app.services import documents, ranking

    now = now or _now()
    today = now.astimezone(local_tz()).date()
    day = str(await get_setting(session, "academic.summary_day") or "")
    if not day or today.strftime("%m-%d") != day:
        return 0
    year = study_year_start(today, str(await get_setting(session, "academic.year_start")))
    start = _start_date(year, str(await get_setting(session, "academic.year_start")))
    members, data = await documents._activity(session, documents.Params(date_from=start, date_to=today))
    places = {entry.user_id: place for place, entry in enumerate(await ranking._standings(session, "season", None), 1)}
    friends = dict(
        (
            await session.execute(
                select(User.referred_by, func.count(User.id))
                .where(
                    User.referred_by.is_not(None),
                    User.deleted_at.is_(None),
                    User.registered_at >= datetime.combine(start, datetime.min.time(), tzinfo=local_tz()),
                )
                .group_by(User.referred_by)
            )
        ).all()
    )
    queued = 0
    for user, _faculty in members:
        if user.status != UserStatus.ACTIVE:
            continue
        values = {key: int(data.get(key, {}).get(user.id, 0)) for key in ("books", "events", "tests", "points")}
        values["certificates"] = int(data.get("certificates", {}).get(user.id, 0))
        values["achievements"] = int(data.get("achievements", {}).get(user.id, 0))
        if not any(values.values()):
            continue
        lines = [f"📖 <b>{year}–{year + 1} o'quv yilingiz yakunlari</b>", ""]
        lines.append(f"📚 O'qilgan kitoblar: <b>{values['books']}</b>")
        lines.append(f"📅 Tadbirlarda qatnashish: <b>{values['events']}</b>")
        lines.append(f"📝 Yechilgan testlar: <b>{values['tests']}</b>")
        lines.append(f"⭐ To'plangan ballar: <b>{values['points']}</b>")
        if user.id in places:
            lines.append(f"🏆 Yillik reytingda: <b>{places[user.id]}-o'rin</b>")
        if values["certificates"]:
            lines.append(f"🎓 Sertifikatlar: <b>{values['certificates']}</b>")
        if values["achievements"]:
            lines.append(f"🏅 Yangi yutuqlar: <b>{values['achievements']}</b>")
        if friends.get(user.id):
            lines.append(f"👥 Klubga olib kelgan do'stlar: <b>{friends[user.id]}</b>")
        lines += ["", "Rahmat, ajoyib yil bo'ldi! Yozgi ta'tilda ham kitobni qo'ldan qo'ymang 📖☀️"]
        await enqueue_notification(
            session,
            user_id=user.id,
            type_=NotificationType.DIGEST,
            text="\n".join(lines),
            dedup_key=f"year-summary:{year}:{user.id}",
            payload={"buttons": [{"text": "📊 Natijalarim", "app_route": "results"}], "mood": "CELEBRATE"},
            priority=4,
        )
        queued += 1
    await session.commit()
    return queued
