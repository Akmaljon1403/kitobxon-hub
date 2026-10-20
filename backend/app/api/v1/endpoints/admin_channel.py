"""Admin Panel: the club's Telegram channel — the bot's posts, a manual post, stickers."""

from __future__ import annotations

import html
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from pydantic import AwareDatetime

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models import ChannelPost
from app.models.enums import ChannelPostKind, ChannelPostStatus
from app.schemas.channel import ChannelOut, ChannelPostOut, ChannelPostTextIn, ChannelStickerOut
from app.security.permissions import Perm
from app.services import channel as channel_service

router = APIRouter(prefix="/admin/channel", tags=["admin: channel"])
Sender = Annotated[CurrentUser, Depends(require_permissions(Perm.NOTIFICATION_SEND))]
MAX_PHOTO_BYTES = 10 * 1024 * 1024


def _post(post: ChannelPost) -> ChannelPostOut:
    return ChannelPostOut(
        id=post.id,
        kind=post.kind,
        text=post.text,
        has_photo=bool(post.photo_key or post.photo_url),
        has_sticker=bool(post.sticker_file_id),
        status=post.status,
        scheduled_at=post.scheduled_at,
        sent_at=post.sent_at,
        last_error=post.last_error,
        manual=post.kind == ChannelPostKind.MANUAL,
        plain_text=channel_service.plain_text(post.text),
        in_review=post.status == ChannelPostStatus.PENDING
        and post.review_sent_at is not None
        and post.reviewed_at is None,
        reviewed_at=post.reviewed_at,
    )


@router.get("", response_model=ChannelOut, summary="Channel status, recent posts and saved stickers")
async def channel_overview(_: Sender, db: DbSession) -> ChannelOut:
    return ChannelOut(
        **await channel_service.status(db),
        posts=[_post(post) for post in await channel_service.recent_posts(db)],
        stickers=[
            ChannelStickerOut(
                id=s.id,
                emoji=s.emoji,
                set_name=s.set_name,
                is_animated=s.is_animated,
                mood=s.mood,
                created_at=s.created_at,
            )
            for s in await channel_service.stickers(db)
        ],
    )


@router.post(
    "/posts",
    response_model=ChannelPostOut,
    status_code=status.HTTP_201_CREATED,
    summary="Post in the channel now or at a set time (multipart: text, optional photo)",
)
async def create_post(
    current: Sender,
    db: DbSession,
    text: Annotated[str, Form(max_length=4000)] = "",
    photo: Annotated[UploadFile | None, File()] = None,
    sticker_id: Annotated[uuid.UUID | None, Form()] = None,
    with_button: Annotated[bool, Form()] = True,
    scheduled_at: Annotated[AwareDatetime | None, Form()] = None,
    target_chat_id: Annotated[str | None, Form()] = None,
) -> ChannelPostOut:
    data = await photo.read(MAX_PHOTO_BYTES + 1) if photo is not None else None
    post = await channel_service.manual_post(
        db,
        actor_id=current.user.id,
        text=text,
        photo=data or None,
        sticker_id=sticker_id,
        with_button=with_button,
        scheduled_at=scheduled_at,
        target_chat_id=target_chat_id,
    )
    return _post(post)


@router.post("/test", response_model=ChannelPostOut, summary="A short test post to check the bot's rights")
async def test_post(current: Sender, db: DbSession) -> ChannelPostOut:
    return _post(await channel_service.test_post(db, actor_id=current.user.id))


@router.post("/posts/{post_id}/cancel", response_model=ChannelPostOut, summary="Cancel a post not sent yet")
async def cancel_post(post_id: uuid.UUID, current: Sender, db: DbSession) -> ChannelPostOut:
    return _post(await channel_service.cancel_post(db, actor_id=current.user.id, post_id=post_id))


@router.post("/posts/{post_id}/publish-now", response_model=ChannelPostOut, summary="Approve: post it right now")
async def publish_now(post_id: uuid.UUID, current: Sender, db: DbSession) -> ChannelPostOut:
    return _post(await channel_service.publish_now(db, actor_id=current.user.id, post_id=post_id))


@router.put(
    "/posts/{post_id}/text",
    response_model=ChannelPostOut,
    summary="New text for a post not sent yet (plain text); it goes out right after",
)
async def edit_post(post_id: uuid.UUID, payload: ChannelPostTextIn, current: Sender, db: DbSession) -> ChannelPostOut:
    post = await channel_service.edit_post(
        db, actor_id=current.user.id, post_id=post_id, text=html.escape(payload.text.strip(), quote=False)
    )
    return _post(post)


@router.delete("/stickers/{sticker_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Forget a saved sticker")
async def delete_sticker(sticker_id: uuid.UUID, current: Sender, db: DbSession) -> Response:
    await channel_service.delete_sticker(db, actor_id=current.user.id, sticker_id=sticker_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
