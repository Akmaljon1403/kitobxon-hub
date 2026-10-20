"""Round O fixes.

* «Hoziroq jo'natish» (publish-now) sends a channel post immediately, even at night — the admin
  chose it consciously, so the club's quiet hours are not applied to a manual publish.
* A test's result is always scaled to its configured maximum, as a whole number — never the raw
  sum of the uploaded questions' points.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelPost
from app.models.enums import ChannelPostKind, ChannelPostStatus
from app.services import channel
from app.services.quizzes import scale
from tests.factories import create_user
from tests.helpers import grant_role

_ids = itertools.count(4_900_000)


async def test_publish_now_sends_immediately_even_at_night(db: AsyncSession) -> None:
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "SUPER_ADMIN")
    # a post left for tomorrow morning, as the night-time auto-scheduler would leave it
    post = ChannelPost(
        kind=ChannelPostKind.MANUAL,
        text="Shoshilinch e'lon",
        status=ChannelPostStatus.PENDING,
        scheduled_at=datetime.now(UTC) + timedelta(hours=14),
        review_sent_at=datetime.now(UTC),
    )
    db.add(post)
    await db.commit()

    await channel.publish_now(db, actor_id=admin.id, post_id=post.id)
    await db.refresh(post)

    # now due (<= now): the sender picks it up at once, not held until the morning
    assert post.scheduled_at <= datetime.now(UTC) + timedelta(seconds=5)
    assert post.reviewed_by == admin.id


def test_score_is_scaled_to_configured_max_whole_number() -> None:
    # a perfect raw (20/20) on a test configured for 10 → exactly 10, never the raw 20
    assert scale(20, 20, 10) == 10
    # half correct → half the configured maximum
    assert scale(10, 20, 10) == 5
    # a fractional result is a whole number (1.5 → 2)
    assert scale(3, 20, 10) == 2
    assert scale(0, 20, 10) == 0
    # it can never exceed the configured maximum, whatever the question points sum to
    assert scale(999, 1000, 10) <= 10
    assert scale(1000, 1000, 7) == 7
