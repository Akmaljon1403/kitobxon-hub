"""«💬 A'zolar fikrlari»: quotes, thoughts, impressions and testimonials members send to the club.

* ``Contribution`` — what a member wrote: shown in the common feed once an admin approves it (or at
  once, if the club allows), kept in the author's own list, and usable by the club: as a card in the
  channel, a message to members, the quote of the day;
* ``ContributionLike`` — one ❤️ of a member.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import ContributionKind, ContributionStatus


class Contribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contributions"
    __table_args__ = (
        Index("ix_contributions_status_created_at", "status", "created_at"),
        Index("ix_contributions_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[ContributionKind] = mapped_column(enum_column(ContributionKind))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255))  # «Muallif — Kitob», shown under the text
    book_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"))
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    saved_quote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("saved_quotes.id", ondelete="SET NULL"))
    show_name: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    style: Mapped[str] = mapped_column(String(16), default="classic", server_default="classic")
    status: Mapped[ContributionStatus] = mapped_column(
        enum_column(ContributionStatus),
        default=ContributionStatus.PENDING,
        server_default=ContributionStatus.PENDING.value,
    )
    featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    likes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    points_awarded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column()
    # Where the club used it: [{"where": "channel" | "members" | "quote_of_day" | "me", "at": ISO, "by": name}]
    uses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default="[]")


class ContributionLike(Base):
    __tablename__ = "contribution_likes"

    contribution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contributions.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PaymentsChatLink(Base):
    """A message of the bot in the payments channel and what it is about, so that an admin's «Reply» to it
    in the channel reaches the right member: a payment question (``ticket``), a card payment (``card``)
    or a member (``user``, e.g. a Telegram Stars payment)."""

    __tablename__ = "payments_chat_links"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[uuid.UUID] = mapped_column()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
