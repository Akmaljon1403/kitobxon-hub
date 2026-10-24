"""The signed-in member's own data."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, DbSession
from app.models import Faculty, UserNotificationSettings
from app.models.enums import FeatureMode
from app.schemas.book import BookOut
from app.schemas.event import EventOut, LiveAttendanceOut
from app.schemas.quiz import TestOut
from app.schemas.user import (
    FacultyOut,
    MemberContestOut,
    MeOut,
    MeUpdateIn,
    NotificationSettingsIn,
    NotificationSettingsOut,
    ReferralBriefOut,
    ReferralOverviewOut,
    SubscriptionChannelOut,
    SubscriptionOut,
)
from app.services import features, premium, referrals, subscription
from app.services import users as user_service
from app.services.passport import member_number
from app.services.settings import get_setting

router = APIRouter(prefix="/me", tags=["me"])


async def _me(current, db) -> MeOut:
    user = current.user
    faculty = await db.get(Faculty, user.faculty_id) if user.faculty_id else None
    return MeOut(
        id=user.id,
        member_number=member_number(user),
        first_name=user.first_name,
        last_name=user.last_name,
        telegram_username=user.telegram_username,
        photo_url=user.photo_url,
        phone=user.phone,
        faculty=FacultyOut(id=faculty.id, name=faculty.name, short_name=faculty.short_name) if faculty else None,
        course=user.course,
        group_name=user.group_name,
        status=user.status,
        registered_at=user.registered_at,
        graduated=user.graduated_at is not None,
        is_admin=current.is_admin,
        roles=sorted(current.roles),
        max_course=await get_setting(db, "registration.max_course"),
        features=await features.access(db, user),
        is_premium=await premium.is_premium(db, user.id),
        premium_until=await premium.premium_until(db, user.id),
        premium_lifetime=await premium.is_lifetime(db, user.id),
        passport_photo=user.passport_photo_key is not None,
        premium_trial=await premium.on_trial(db, user.id),
        premium_features=sorted(
            code for code, mode in (await features.modes(db)).items() if mode == FeatureMode.PREMIUM
        ),
        subscription_missing=[]
        if current.is_admin
        else [
            SubscriptionChannelOut(**item)
            for item in subscription.as_dicts(await subscription.missing(db, user.telegram_id))
        ],
    )


@router.get("", response_model=MeOut, summary="My profile")
async def get_me(current: CurrentUserDep, db: DbSession) -> MeOut:
    return await _me(current, db)


class HomeOut(BaseModel):
    """What the Mini App home screen shows, gathered in a single request so it opens with one round
    trip instead of four. The points badge stays its own call (`/me/ranking`) because it is feature-gated."""

    book: BookOut | None = None  # the club's active book
    event: EventOut | None = None  # the next upcoming event
    test: TestOut | None = None  # an open test the member can still take
    attendance: LiveAttendanceOut | None = None  # an event whose check-in is open right now


@router.get("/home", response_model=HomeOut, summary="The home screen's data in one request")
async def home(current: CurrentUserDep, db: DbSession) -> HomeOut:
    # Reuse the very same member endpoints the home used to call separately — one HTTP round trip now.
    from app.api.v1.endpoints.books import list_books
    from app.api.v1.endpoints.events import list_events, open_attendance
    from app.api.v1.endpoints.quizzes import list_tests

    books = await list_books(current, db, limit=3, offset=0)
    book = next((item for item in books.items if item.status == "ACTIVE"), None)
    events = await list_events(current, db, scope="upcoming", limit=1, offset=0)
    event = events.items[0] if events.items else None
    tests = await list_tests(current, db)
    test = next((item for item in tests if item.state == "OPEN" and (item.in_progress or not item.attempts)), None)
    attendance = await open_attendance(current, db)
    live = next((item for item in attendance if not item.checked_in), None)
    return HomeOut(book=book, event=event, test=test, attendance=live)


@router.get("/subscription", response_model=SubscriptionOut, summary="Am I subscribed to the required channels?")
async def my_subscription(
    current: CurrentUserDep, db: DbSession, fresh: Annotated[bool, Query()] = False
) -> SubscriptionOut:
    channels = [] if current.is_admin else await subscription.missing(db, current.user.telegram_id, fresh=fresh)
    return SubscriptionOut(
        ok=not channels, channels=[SubscriptionChannelOut(**item) for item in subscription.as_dicts(channels)]
    )


@router.patch("", response_model=MeOut, summary="Correct my faculty, course or group")
async def update_me(payload: MeUpdateIn, current: CurrentUserDep, db: DbSession) -> MeOut:
    await user_service.update_my_profile(db, current.user, payload.model_dump(exclude_unset=True))
    return await _me(current, db)


def _settings_out(settings: UserNotificationSettings) -> NotificationSettingsOut:
    return NotificationSettingsOut(**{field: getattr(settings, field) for field in user_service.NOTIFICATION_FIELDS})


@router.get("/notification-settings", response_model=NotificationSettingsOut, summary="My reminder preferences")
async def get_notification_settings(current: CurrentUserDep, db: DbSession) -> NotificationSettingsOut:
    return _settings_out(await user_service.get_notification_settings(db, current.user.id))


@router.put("/notification-settings", response_model=NotificationSettingsOut, summary="Change reminder preferences")
async def update_notification_settings(
    payload: NotificationSettingsIn, current: CurrentUserDep, db: DbSession
) -> NotificationSettingsOut:
    settings = await user_service.update_notification_settings(
        db, current.user.id, payload.model_dump(exclude_unset=True)
    )
    return _settings_out(settings)


@router.get(
    "/referrals",
    response_model=ReferralOverviewOut,
    summary="My invitation link, «Sizning foydangiz» (what my friends did) and the inviters' table",
)
async def my_referrals(current: CurrentUserDep, db: DbSession) -> ReferralOverviewOut:
    return ReferralOverviewOut(**await referrals.overview(db, current.user))


@router.get(
    "/referrals/brief",
    response_model=ReferralBriefOut,
    summary="«🎁 Sizning foydangiz» in short: my link, how many friends I invited and their points",
)
async def my_referrals_brief(current: CurrentUserDep, db: DbSession) -> ReferralBriefOut:
    summary = await referrals.summary(db, current.user)
    return ReferralBriefOut(**summary, impact=await referrals.impact(db, current.user))


@router.get(
    "/referral-contests",
    response_model=list[MemberContestOut],
    summary="Referral contests: running, upcoming and recently finished (as the club lets members see them)",
)
async def my_referral_contests(current: CurrentUserDep, db: DbSession) -> list[MemberContestOut]:
    from app.services import contests

    return [MemberContestOut(**item) for item in await contests.for_member(db, current.user)]


class SupportMessageOut(BaseModel):
    id: uuid.UUID
    from_admin: bool
    text: str
    created_at: datetime


class SupportIn(BaseModel):
    text: str = Field(min_length=2, max_length=2000)
    topic: Literal["general", "payment"] = "general"


@router.get("/support", response_model=list[SupportMessageOut], summary="My conversation with the club")
async def my_support(current: CurrentUserDep, db: DbSession) -> list[SupportMessageOut]:
    from app.services import support

    return [
        SupportMessageOut(id=m.id, from_admin=m.from_admin, text=m.text, created_at=m.created_at)
        for m in await support.member_thread(db, current.user.id)
    ]


@router.post(
    "/support", response_model=list[SupportMessageOut], summary="Write to the club (the answer also comes in the bot)"
)
async def write_support(payload: SupportIn, current: CurrentUserDep, db: DbSession) -> list[SupportMessageOut]:
    from app.services import support

    await features.require(db, current.user, "support")
    await support.member_message(
        db, user=current.user, text=payload.text, topic="payment" if payload.topic == "payment" else None
    )
    await db.commit()
    return await my_support(current, db)
