"""«💬 A'zolar fikrlari» for members: write a quote, a thought, an impression or a testimonial; read the
common feed; ❤️; your own list; every text as a card in six designs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from aiogram.types import BufferedInputFile
from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUserDep, DbSession, feature_required
from app.models.enums import ContributionKind, ContributionStatus
from app.services import community, delivery

router = APIRouter(prefix="/community", tags=["community"], dependencies=[feature_required("community")])
PNG = {200: {"content": {"image/png": {}}}}


class ContributionIn(BaseModel):
    kind: ContributionKind
    text: str = Field(min_length=community.MIN_TEXT, max_length=community.MAX_TEXT)
    source: str | None = Field(default=None, max_length=community.MAX_SOURCE)
    book_id: uuid.UUID | None = None
    event_id: uuid.UUID | None = None
    show_name: bool = True
    style: str | None = Field(default=None, max_length=16)


class ContributionOut(BaseModel):
    id: uuid.UUID
    kind: ContributionKind
    kind_title: str
    text: str
    source: str | None
    author: str
    show_name: bool
    style: str
    status: ContributionStatus
    featured: bool
    likes: int
    liked: bool
    book_id: uuid.UUID | None
    event_id: uuid.UUID | None
    in_channel: bool
    created_at: datetime


class OptionsOut(BaseModel):
    kinds: list[dict[str, str]]
    styles: list[dict[str, str]]
    books: list[dict[str, str | uuid.UUID | None]]
    events: list[dict[str, str | uuid.UUID | datetime | None]]


@router.get("", response_model=list[ContributionOut], summary="The common feed")
async def feed(
    current: CurrentUserDep,
    db: DbSession,
    kind: ContributionKind | None = None,
    sort: Literal["new", "top"] = "new",
    limit: Annotated[int, Query(ge=1, le=50)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    return await community.feed(db, current.user, kind=kind, sort=sort, limit=limit, offset=offset)


@router.get("/mine", response_model=list[ContributionOut], summary="What I sent (with its status)")
async def mine(current: CurrentUserDep, db: DbSession) -> list[dict]:
    return await community.mine(db, current.user)


@router.get("/options", response_model=OptionsOut, summary="Kinds, card designs, books and my events to write about")
async def options(current: CurrentUserDep, db: DbSession) -> dict:
    return await community.book_options(db, current.user)


@router.post("", response_model=ContributionOut, status_code=status.HTTP_201_CREATED, summary="Send a text")
async def submit(payload: ContributionIn, current: CurrentUserDep, db: DbSession) -> dict:
    item = await community.submit(db, current.user, **payload.model_dump())
    return community.describe(item, current.user, None)


@router.delete("/{contribution_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Take my text back")
async def delete(contribution_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> Response:
    await community.delete_own(db, current.user, contribution_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{contribution_id}/like", response_model=dict[str, bool | int], summary="❤️ on or off")
async def like(contribution_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> dict[str, bool | int]:
    liked, likes = await community.like(db, current.user, contribution_id)
    return {"liked": liked, "likes": likes}


@router.get("/{contribution_id}/card.png", response_class=Response, responses=PNG, summary="The text as a card")
async def card(
    contribution_id: uuid.UUID,
    current: CurrentUserDep,
    db: DbSession,
    style: Annotated[str | None, Query(max_length=16)] = None,
) -> Response:
    item, user, faculty = await community.visible(db, current.user, contribution_id)
    image = await community.card_png(db, item, user, faculty, style)
    return Response(content=image, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.post("/{contribution_id}/send", response_model=dict[str, bool], summary="The bot sends me the card")
async def send_card(
    contribution_id: uuid.UUID,
    current: CurrentUserDep,
    db: DbSession,
    style: Annotated[str | None, Query(max_length=16)] = None,
) -> dict[str, bool]:
    item, user, faculty = await community.visible(db, current.user, contribution_id)
    image = await community.card_png(db, item, user, faculty, style)
    bot = delivery.runtime_bot()
    await delivery.explain_failures(
        bot.send_photo(
            current.user.telegram_id,
            BufferedInputFile(image, filename=community.card_filename(item)),
            caption="💬 Kartochka tayyor — do'stlaringizga ulashing (rasmni bosib turing → «Ulashish»).",
        )
    )
    return {"sent": True}
