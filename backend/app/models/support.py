"""Messages from members to the club's administrators ("Adminga yozish").

A member writes through the bot; administrators answer from the Admin Panel or the bot. Members
never learn which administrator answered: replies are signed by the club.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, func
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import SupportTicketStatus


class SupportTicket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_support_tickets_status_last_message_at", "status", "last_message_at"),
        Index("ix_support_tickets_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[SupportTicketStatus] = mapped_column(
        enum_column(SupportTicketStatus), default=SupportTicketStatus.OPEN, server_default="OPEN"
    )
    last_message_at: Mapped[datetime] = mapped_column(server_default=func.now())
    unread_for_admin: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql_text("true"))


class SupportMessage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "support_messages"
    __table_args__ = (Index("ix_support_messages_ticket_id_created_at", "ticket_id", "created_at"),)

    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id", ondelete="CASCADE"))
    from_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("false"))
    # Internal only (accountability in the Admin Panel); never shown to members.
    admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    # Telegram file id of an attached photo (downloaded through the bot when an admin opens it).
    photo_file_id: Mapped[str | None] = mapped_column(String(256))
