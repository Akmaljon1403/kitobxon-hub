"""Short-lived links for files a member saves from the Mini App.

Telegram's ``downloadFile`` needs a plain HTTPS address that works without our sign-in header,
so the Mini App asks for a link that is signed by the server and expires after a few minutes.
"""

from __future__ import annotations

import time
import uuid

from app.core.errors import NotFoundError
from app.security.crypto import constant_time_equals, keyed_hash

TTL_SECONDS = 300
KINDS = ("passport", "certificate", "portfolio")


def _signature(body: str) -> str:
    return keyed_hash("download-link", body)[:32]


def make_token(kind: str, object_id: uuid.UUID, *, now: float | None = None) -> str:
    assert kind in KINDS
    expires = int((now or time.time()) + TTL_SECONDS)
    body = f"{kind}.{object_id.hex}.{expires}"
    return f"{body}.{_signature(body)}"


def read_token(token: str, *, now: float | None = None) -> tuple[str, uuid.UUID]:
    expired = NotFoundError("LINK_EXPIRED", "Havola eskirgan. Ilovada «Yuklab olish»ni qayta bosing.")
    parts = token.split(".")
    if len(parts) != 4 or parts[0] not in KINDS:
        raise expired
    kind, object_hex, expires, signature = parts
    if not constant_time_equals(_signature(f"{kind}.{object_hex}.{expires}"), signature):
        raise expired
    try:
        if int(expires) < (now or time.time()):
            raise expired
        return kind, uuid.UUID(hex=object_hex)
    except ValueError as exc:
        raise expired from exc
