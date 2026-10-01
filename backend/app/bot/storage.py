"""aiogram FSM storage backed by the ``bot_fsm_states`` PostgreSQL table.

Only JSON-serialisable values (strings, numbers, booleans, lists, dicts) may be put
into the FSM data; handlers store UUIDs as strings.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, DefaultKeyBuilder, KeyBuilder, StateType, StorageKey
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.database import get_session_factory
from app.models import BotFsmState


class PostgresStorage(BaseStorage):
    def __init__(self, key_builder: KeyBuilder | None = None) -> None:
        self.key_builder = key_builder or DefaultKeyBuilder(with_bot_id=True, with_destiny=True)

    def _key(self, key: StorageKey) -> str:
        return self.key_builder.build(key)

    async def _write(self, key: StorageKey, values: dict[str, Any]) -> None:
        storage_key = self._key(key)
        statement = insert(BotFsmState).values(key=storage_key, **values)
        statement = statement.on_conflict_do_update(index_elements=[BotFsmState.key], set_=values)
        async with get_session_factory()() as session:
            await session.execute(statement)
            # Rows without state and data carry no information; keep the table small.
            await session.execute(
                delete(BotFsmState).where(
                    BotFsmState.key == storage_key,
                    BotFsmState.state.is_(None),
                    BotFsmState.data == text("'{}'::jsonb"),
                )
            )
            await session.commit()

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        value = state.state if isinstance(state, State) else state
        await self._write(key, {"state": value})

    async def get_state(self, key: StorageKey) -> str | None:
        async with get_session_factory()() as session:
            return await session.scalar(select(BotFsmState.state).where(BotFsmState.key == self._key(key)))

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await self._write(key, {"data": dict(data)})

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with get_session_factory()() as session:
            data = await session.scalar(select(BotFsmState.data).where(BotFsmState.key == self._key(key)))
        return dict(data or {})

    async def close(self) -> None:
        return None
