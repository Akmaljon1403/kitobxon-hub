"""Small cryptographic helpers built only on the standard library."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.core.config import get_settings


def derive_key(purpose: str) -> bytes:
    """Derive an independent 256-bit key for one purpose (JWT signing, attendance codes, ...).

    Using separate keys means a weakness in one feature never exposes another one.
    """
    master = get_settings().secret_key.get_secret_value().encode()
    return hmac.new(master, f"kitobxon-hub:{purpose}".encode(), hashlib.sha256).digest()


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def keyed_hash(purpose: str, value: str) -> str:
    """HMAC-SHA256 of ``value`` with a purpose-specific key (for short secrets such as 6-char codes)."""
    return hmac.new(derive_key(purpose), value.encode(), hashlib.sha256).hexdigest()


def random_token(num_bytes: int = 32) -> str:
    return secrets.token_urlsafe(num_bytes)


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
