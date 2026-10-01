"""Declarative base, naming conventions and shared column mixins."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any, ClassVar

from sqlalchemy import BigInteger, Date, DateTime, Enum, MetaData, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names make Alembic migrations stable and readable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Fetch server-generated values (updated_at, defaults) with RETURNING right after INSERT/UPDATE,
    # so objects stay usable after a commit without lazy loads (required with asyncio).
    __mapper_args__: ClassVar[dict[str, Any]] = {"eager_defaults": True}
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: DateTime(timezone=True),
        date: Date,
        uuid.UUID: Uuid,
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
    }


def enum_column(enum_cls: type[enum.Enum], **kwargs: Any) -> Any:
    """Stores an enum as VARCHAR + CHECK constraint (easier to evolve than native PG enums)."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
        name=f"{enum_cls.__name__.lower()}",
        **kwargs,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"), sort_order=-100
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False, sort_order=100)


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False, sort_order=101
    )


class SoftDeleteMixin:
    """Rows are hidden instead of deleted so history (scores, reports) stays intact."""

    deleted_at: Mapped[datetime | None] = mapped_column(default=None, sort_order=102)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


TelegramId = BigInteger
