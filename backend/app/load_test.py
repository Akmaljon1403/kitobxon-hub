"""Load test: many members open the Mini App at the same time (e.g. right after a test is announced).

Run it against a test copy, never the real club — it fills the database with made-up members:

    # 1) an empty database and the server (same DATABASE_URL and SECRET_KEY in both terminals)
    alembic upgrade head && uvicorn app.main:app --workers 2
    # 2) the load
    python -m app.load_test --seed 3000 --concurrency 200 --requests 6000

Every simulated member does what the app does on opening: profile, books, events, tests, rankings.
The report shows the answer times (median / 95% / slowest) and the errors for every screen.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import Book, Event, ScoreTransaction, Season, Test, User
from app.models.enums import BookStatus, EventStatus, ScoreCategory, TestStatus, UserStatus
from app.security.tokens import create_access_token
from app.services.bootstrap import sync_reference_data

APP_OPENING = (
    "/api/v1/me",
    "/api/v1/meta",
    "/api/v1/books",
    "/api/v1/events",
    "/api/v1/tests",
    "/api/v1/rankings",
    "/api/v1/me/ranking",
    "/api/v1/me/stats",
    "/api/v1/me/achievements",
)
_rng = random.SystemRandom()
LOAD_MARK = "Yuklama"  # every made-up member carries this last name


async def seed(members: int) -> list[User]:
    """Made-up members with points, plus a few books, events and tests (only once)."""
    settings = get_settings()
    if settings.environment == "production":
        raise SystemExit("The load test never runs against production.")
    factory = get_session_factory()
    async with factory() as session:
        await sync_reference_data(session)
        have = int(await session.scalar(select(func.count(User.id)).where(User.last_name == LOAD_MARK)) or 0)
        season = await session.scalar(select(Season).where(Season.is_current.is_(True)))
        now = datetime.now(UTC)
        start = 10_000_000_000
        for chunk_start in range(have, members, 1000):
            batch = [
                User(
                    telegram_id=start + number,
                    first_name=f"A'zo{number}",
                    last_name=LOAD_MARK,
                    phone=f"+99899{number:07d}",
                    course=number % 6 + 1,
                    group_name=f"{number % 6 + 1}0{number % 9 + 1}",
                    status=UserStatus.ACTIVE,
                    registered_at=now,
                )
                for number in range(chunk_start, min(members, chunk_start + 1000))
            ]
            session.add_all(batch)
            await session.flush()
            session.add_all(
                ScoreTransaction(
                    user_id=user.id,
                    season_id=season.id if season else None,
                    amount=_rng.randint(1, 300),
                    category=ScoreCategory.TEST,
                    idempotency_key=f"load:{user.telegram_id}",
                )
                for user in batch
            )
            await session.commit()
        if not await session.scalar(select(func.count(Book.id))):
            for number in range(20):
                session.add(Book(title=f"Kitob {number}", author="Muallif", status=BookStatus.ACTIVE))
            for number in range(10):
                begins = now + timedelta(days=number - 5)
                session.add(
                    Event(
                        title=f"Tadbir {number}",
                        location="Kutubxona",
                        starts_at=begins,
                        ends_at=begins + timedelta(hours=2),
                        attendance_opens_at=begins,
                        attendance_closes_at=begins + timedelta(minutes=15),
                        status=EventStatus.PUBLISHED,
                    )
                )
                session.add(
                    Test(
                        title=f"Test {number}",
                        starts_at=begins,
                        ends_at=begins + timedelta(days=1),
                        duration_minutes=15,
                        max_score=20,
                        passing_score=10,
                        status=TestStatus.PUBLISHED,
                    )
                )
            await session.commit()
        return list(await session.scalars(select(User).where(User.last_name == LOAD_MARK).limit(members)))


async def run(base_url: str, users: list[User], concurrency: int, total: int) -> dict[str, list[float]]:
    tokens = [create_access_token(user.id, user.token_version, "member")[0] for user in users]
    timings: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    for _ in range(total):
        queue.put_nowait((_rng.choice(APP_OPENING), _rng.choice(tokens)))

    async def worker(client: httpx.AsyncClient) -> None:
        while not queue.empty():
            path, token = queue.get_nowait()
            began = time.perf_counter()
            try:
                response = await client.get(path, headers={"Authorization": f"Bearer {token}"})
                status = response.status_code
            except httpx.HTTPError:
                status = 0
            timings[path].append(time.perf_counter() - began)
            if status != 200:
                errors[path][status] += 1

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    began = time.perf_counter()
    async with httpx.AsyncClient(base_url=base_url, timeout=60, limits=limits) as client:
        await asyncio.gather(*(worker(client) for _ in range(concurrency)))
    elapsed = time.perf_counter() - began

    print(f"\n{total} so'rov, {concurrency} parallel, {elapsed:.1f} s — {total / elapsed:.0f} so'rov/soniya\n")
    print(f"{'Ekran':32} {'soni':>6} {'median':>8} {'95%':>8} {'eng sekin':>10}  xatolar")
    for path in APP_OPENING:
        values = sorted(timings[path])
        if not values:
            continue
        p95 = values[int(len(values) * 0.95) - 1] if len(values) > 1 else values[0]
        failed = ", ".join(f"{code}×{count}" for code, count in errors[path].items()) or "—"
        print(
            f"{path:32} {len(values):6} {statistics.median(values) * 1000:7.0f}ms "
            f"{p95 * 1000:7.0f}ms {values[-1] * 1000:9.0f}ms  {failed}"
        )
    return timings


async def main() -> None:
    parser = argparse.ArgumentParser(prog="load_test")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--seed", type=int, default=3000, help="how many made-up members")
    parser.add_argument("--concurrency", type=int, default=200)
    parser.add_argument("--requests", type=int, default=6000)
    args = parser.parse_args()
    users = await seed(args.seed)
    await run(args.url, users, args.concurrency, args.requests)


if __name__ == "__main__":
    asyncio.run(main())
