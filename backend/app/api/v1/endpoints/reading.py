"""«📚 Mening mutolaam» for members: the bookshelf and reading diary, «Kitobdan keyin 3 savol», the quote
box with shareable cards, personal missions and «🪪 Kitobxonlik kartam»."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime
from typing import Annotated

from aiogram.types import BufferedInputFile
from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, DbSession, feature_required
from app.models import SavedQuote
from app.models.enums import MissionMetric, ShelfStatus, UserMissionStatus
from app.services import delivery, missions, reading_journal, share_cards

router = APIRouter(prefix="/me", tags=["my reading"])
PNG = {200: {"content": {"image/png": {}}}}


# ---------------------------------------------------------------------------- schemas


class ShelfItemOut(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID | None
    club_book: bool
    title: str
    author: str | None
    cover_url: str | None
    status: ShelfStatus
    pages_total: int | None
    pages_read: int
    percent: int | None
    rating: int | None
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class DayPages(BaseModel):
    date: date
    pages: int


class ReadingStatsOut(BaseModel):
    today_pages: int
    week_pages: int
    month_pages: int
    year_pages: int
    streak: int = Field(description="Reading days in a row up to today (or yesterday)")
    best_streak: int
    month_days: int
    finished_this_year: int
    shelf: dict[str, int]
    quotes: int
    reflections: int
    last_days: list[DayPages]


class ShelfOut(BaseModel):
    items: list[ShelfItemOut]
    stats: ReadingStatsOut


class ShelfAddIn(BaseModel):
    book_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    author: str | None = Field(default=None, max_length=255)
    pages_total: int | None = Field(default=None, gt=0, le=20000)
    status: ShelfStatus = ShelfStatus.WANT


class ShelfUpdateIn(BaseModel):
    status: ShelfStatus | None = None
    pages_total: int | None = Field(default=None, gt=0, le=20000)
    rating: int | None = Field(default=None, ge=1, le=5)
    clear_rating: bool = False


class LogIn(BaseModel):
    pages: int = Field(gt=0, le=2000)
    minutes: int | None = Field(default=None, gt=0, le=1440)
    note: str | None = Field(default=None, max_length=1000)
    day: date | None = Field(default=None, description="The day read (today when empty; up to 7 days back)")


class LogOut(BaseModel):
    id: uuid.UUID
    shelf_item_id: uuid.UUID
    title: str
    log_date: date
    pages: int
    minutes: int | None
    note: str | None


class ReflectionIn(BaseModel):
    main_idea: str = Field(max_length=1500)
    favorite_moment: str = Field(max_length=1500)
    apply_in_life: str = Field(max_length=1500)


class ReflectionOut(BaseModel):
    main_idea: str
    favorite_moment: str
    apply_in_life: str
    updated_at: datetime
    points: int = 0  # points given by this save


class QuoteIn(BaseModel):
    text: str | None = Field(default=None, max_length=1000)
    book_quote_id: uuid.UUID | None = None
    shelf_item_id: uuid.UUID | None = None
    page: int | None = Field(default=None, gt=0, le=20000)
    note: str | None = Field(default=None, max_length=500)


class QuoteOut(BaseModel):
    id: uuid.UUID
    text: str
    source: str | None
    page: int | None
    note: str | None
    shelf_item_id: uuid.UUID | None
    book_quote_id: uuid.UUID | None
    created_at: datetime


class ShelfItemDetailOut(ShelfItemOut):
    diary: list[LogOut]
    reflection: ReflectionOut | None
    quotes: list[QuoteOut]


class MissionOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    icon: str
    metric: MissionMetric
    unit: str
    target: int
    period_days: int
    reward_points: int
    status: UserMissionStatus | None
    progress: int
    started_at: datetime | None
    deadline: datetime | None
    completed_at: datetime | None
    attempts: int


def _quote_out(quote: SavedQuote) -> QuoteOut:
    return QuoteOut(
        id=quote.id,
        text=quote.text,
        source=quote.source,
        page=quote.page,
        note=quote.note,
        shelf_item_id=quote.shelf_item_id,
        book_quote_id=quote.book_quote_id,
        created_at=quote.created_at,
    )


async def _item_out(db: DbSession, current: CurrentUserDep, item_id: uuid.UUID) -> ShelfItemOut:
    item, book = await reading_journal.get_item(db, current.user, item_id)
    return ShelfItemOut(**reading_journal.describe(item, book))


# ---------------------------------------------------------------------------- the shelf and the diary

shelf_router = APIRouter(dependencies=[feature_required("shelf")])


@shelf_router.get("/shelf", response_model=ShelfOut, summary="«📚 Javonim»: my books and my reading numbers")
async def my_shelf(current: CurrentUserDep, db: DbSession) -> ShelfOut:
    items = await reading_journal.shelf(db, current.user)
    return ShelfOut(
        items=[ShelfItemOut(**item) for item in items],
        stats=ReadingStatsOut(**await reading_journal.stats(db, current.user)),
    )


@shelf_router.post("/shelf", response_model=ShelfItemOut, status_code=status.HTTP_201_CREATED, summary="Add a book")
async def add_to_shelf(payload: ShelfAddIn, current: CurrentUserDep, db: DbSession) -> ShelfItemOut:
    item = await reading_journal.add(db, current.user, **payload.model_dump())
    return await _item_out(db, current, item.id)


@shelf_router.get("/shelf/{item_id}", response_model=ShelfItemDetailOut, summary="A book on my shelf, in full")
async def shelf_item(item_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> ShelfItemDetailOut:
    base = await _item_out(db, current, item_id)
    reflection = await reading_journal.reflection(db, current.user, item_id)
    return ShelfItemDetailOut(
        **base.model_dump(),
        diary=[LogOut(**entry) for entry in await reading_journal.diary(db, current.user, item_id=item_id)],
        reflection=ReflectionOut(
            main_idea=reflection.main_idea,
            favorite_moment=reflection.favorite_moment,
            apply_in_life=reflection.apply_in_life,
            updated_at=reflection.updated_at,
        )
        if reflection
        else None,
        quotes=[_quote_out(quote) for quote in await reading_journal.quotes(db, current.user, item_id=item_id)],
    )


@shelf_router.patch("/shelf/{item_id}", response_model=ShelfItemOut, summary="Status, pages or my rating")
async def update_shelf_item(
    item_id: uuid.UUID, payload: ShelfUpdateIn, current: CurrentUserDep, db: DbSession
) -> ShelfItemOut:
    await reading_journal.update(db, current.user, item_id, **payload.model_dump())
    return await _item_out(db, current, item_id)


@shelf_router.delete("/shelf/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Take a book off my shelf")
async def remove_from_shelf(item_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> Response:
    await reading_journal.remove(db, current.user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@shelf_router.post(
    "/shelf/{item_id}/logs", response_model=ShelfItemOut, summary="«Bugun 25 bet o'qidim» (the reading diary)"
)
async def log_pages(item_id: uuid.UUID, payload: LogIn, current: CurrentUserDep, db: DbSession) -> ShelfItemOut:
    await reading_journal.log_pages(
        db, current.user, item_id, pages=payload.pages, minutes=payload.minutes, note=payload.note, day=payload.day
    )
    return await _item_out(db, current, item_id)


@shelf_router.get("/diary", response_model=list[LogOut], summary="My reading diary, newest first")
async def my_diary(
    current: CurrentUserDep, db: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 60
) -> list[LogOut]:
    return [LogOut(**entry) for entry in await reading_journal.diary(db, current.user, limit=limit)]


@shelf_router.delete("/diary/{log_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a diary entry")
async def delete_log(log_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> Response:
    await reading_journal.delete_log(db, current.user, log_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@shelf_router.put(
    "/shelf/{item_id}/reflection", response_model=ReflectionOut, summary="«Kitobdan keyin 3 savol» (points once)"
)
async def save_reflection(
    item_id: uuid.UUID, payload: ReflectionIn, current: CurrentUserDep, db: DbSession
) -> ReflectionOut:
    saved, points = await reading_journal.save_reflection(db, current.user, item_id, **payload.model_dump())
    return ReflectionOut(
        main_idea=saved.main_idea,
        favorite_moment=saved.favorite_moment,
        apply_in_life=saved.apply_in_life,
        updated_at=saved.updated_at,
        points=points,
    )


# ---------------------------------------------------------------------------- the quote box

quotes_router = APIRouter(dependencies=[feature_required("quote_box")])


@quotes_router.get("/quotes", response_model=list[QuoteOut], summary="«💬 Iqtiboslar sandig'i»")
async def my_quotes(
    current: CurrentUserDep, db: DbSession, search: Annotated[str | None, Query(max_length=100)] = None
) -> list[QuoteOut]:
    return [_quote_out(quote) for quote in await reading_journal.quotes(db, current.user, search=search)]


@quotes_router.post(
    "/quotes", response_model=QuoteOut, status_code=status.HTTP_201_CREATED, summary="Save a quote (typed or club)"
)
async def save_quote(payload: QuoteIn, current: CurrentUserDep, db: DbSession) -> QuoteOut:
    return _quote_out(await reading_journal.save_quote(db, current.user, **payload.model_dump()))


@quotes_router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a saved quote")
async def delete_quote(quote_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> Response:
    await reading_journal.delete_quote(db, current.user, quote_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _quote_png(db: DbSession, current: CurrentUserDep, quote_id: uuid.UUID) -> bytes:
    from app.bot.setup import resolve_bot_username

    quote = await reading_journal.get_quote(db, current.user, quote_id)
    footer = share_cards.footer_text(await resolve_bot_username())
    return await asyncio.to_thread(
        share_cards.quote_card, quote.text, quote.source, share_cards.display(current.user), footer
    )


@quotes_router.get(
    "/quotes/{quote_id}/card.png", response_class=Response, responses=PNG, summary="The quote as a picture"
)
async def quote_card(quote_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> Response:
    return Response(content=await _quote_png(db, current, quote_id), media_type="image/png")


@quotes_router.post("/quotes/{quote_id}/send", response_model=dict[str, bool], summary="The bot sends me the card")
async def send_quote_card(quote_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> dict[str, bool]:
    image = await _quote_png(db, current, quote_id)
    bot = delivery.runtime_bot()
    await delivery.explain_failures(
        bot.send_photo(
            current.user.telegram_id,
            BufferedInputFile(image, filename=share_cards.quote_filename(quote_id)),
            caption="💬 Iqtibosingiz kartochkasi — do'stlaringizga ulashing (rasmni bosib turing → «Ulashish»).",
        )
    )
    return {"sent": True}


# ---------------------------------------------------------------------------- personal missions

missions_router = APIRouter(dependencies=[feature_required("missions")])


@missions_router.get("/missions", response_model=list[MissionOut], summary="«🎯 Missiyalar» with my progress")
async def my_missions(current: CurrentUserDep, db: DbSession) -> list[MissionOut]:
    return [MissionOut(**item) for item in await missions.for_member(db, current.user)]


@missions_router.post("/missions/{mission_id}/take", response_model=list[MissionOut], summary="Take a mission")
async def take_mission(mission_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> list[MissionOut]:
    await missions.take(db, current.user, mission_id)
    return [MissionOut(**item) for item in await missions.for_member(db, current.user)]


@missions_router.post("/missions/{mission_id}/give-up", response_model=list[MissionOut], summary="Stop a mission")
async def give_up_mission(mission_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> list[MissionOut]:
    await missions.give_up(db, current.user, mission_id)
    return [MissionOut(**item) for item in await missions.for_member(db, current.user)]


# ---------------------------------------------------------------------------- «🪪 Kitobxonlik kartam»

card_router = APIRouter(dependencies=[feature_required("reading_card")])


async def _card_png(db: DbSession, current: CurrentUserDep) -> bytes:
    from app.bot.setup import resolve_bot_username

    data = await share_cards.reading_card_data(db, current.user, share_cards.footer_text(await resolve_bot_username()))
    return await asyncio.to_thread(share_cards.reading_card, data)


@card_router.get("/reading-card.png", response_class=Response, responses=PNG, summary="«Kitobxonlik kartam» picture")
async def reading_card(current: CurrentUserDep, db: DbSession) -> Response:
    return Response(content=await _card_png(db, current), media_type="image/png")


@card_router.post("/reading-card/send", response_model=dict[str, bool], summary="The bot sends me my reading card")
async def send_reading_card(current: CurrentUserDep, db: DbSession) -> dict[str, bool]:
    image = await _card_png(db, current)
    bot = delivery.runtime_bot()
    await delivery.explain_failures(
        bot.send_photo(
            current.user.telegram_id,
            BufferedInputFile(image, filename=share_cards.card_filename(current.user)),
            caption="🪪 Kitobxonlik kartangiz — do'stlaringizga ulashing va ularni ham klubga taklif qiling!",
        )
    )
    return {"sent": True}


router.include_router(shelf_router)
router.include_router(quotes_router)
router.include_router(missions_router)
router.include_router(card_router)
