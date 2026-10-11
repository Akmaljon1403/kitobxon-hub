"""The club's brand pictures, supplied by the owners and kept in ``app/brand`` (see the README there).

Every picture is optional: when a file is missing, the place it would fill is simply left out.

* ``logo-mark.png`` — the mark: above the certificate title, the report header, the verification page;
* ``logo-horizontal.png`` — the horizontal logo: the portfolio header;
* ``seal.png`` — the round seal over the certificate signature (``seal-light.png``, if present, is used
  on dark certificate designs);
* ``bot-avatar.png`` / ``bot-avatar.jpg`` — the bot's profile photo.
"""

from __future__ import annotations

import base64
import io
from functools import cache
from pathlib import Path

BRAND = Path(__file__).resolve().parent.parent / "brand"


def _find(stem: str) -> Path | None:
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        path = BRAND / f"{stem}{suffix}"
        if path.is_file():
            return path
    return None


@cache
def data_uri(stem: str, max_px: int = 800) -> str | None:
    """A picture as a PNG data URI, at most ``max_px`` on its longer side (None when missing)."""
    from PIL import Image

    path = _find(stem)
    if path is None:
        return None
    with Image.open(path) as image:
        picture = image.convert("RGBA")
    picture.thumbnail((max_px, max_px))
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG", optimize=True)
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"


def _is_dark(color: str) -> bool:
    value = color.lstrip("#")
    if len(value) != 6:
        return False
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue < 110


def seal(enabled: bool, paper: str) -> str | None:
    """The seal for a certificate whose paper colour is ``paper``."""
    if not enabled:
        return None
    if _is_dark(paper) and _find("seal-light") is not None:
        return data_uri("seal-light", 600)
    return data_uri("seal", 600)


def logo_mark() -> str | None:
    return data_uri("logo-mark", 512)


def logo_horizontal() -> str | None:
    return data_uri("logo-horizontal", 1200)


def avatar_jpeg() -> bytes | None:
    """The bot's profile photo as a square JPEG (Telegram crops the circle itself)."""
    from PIL import Image

    path = _find("bot-avatar")
    if path is None:
        return None
    with Image.open(path) as image:
        picture = image.convert("RGB")
    side = min(picture.size)
    left, top = (picture.width - side) // 2, (picture.height - side) // 2
    picture = picture.crop((left, top, left + side, top + side)).resize((640, 640))
    buffer = io.BytesIO()
    picture.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()
