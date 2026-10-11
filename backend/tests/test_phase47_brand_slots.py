"""Round G3: the club's own pictures (logo, seal, avatar) fill their places once they are put in
``app/brand``; until then nothing is shown and nothing breaks."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import brand, certificates
from app.services.report_pdf import _environment
from app.services.settings import update_setting
from tests.factories import create_user


@pytest.fixture
def pictures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(brand, "BRAND", tmp_path)
    brand.data_uri.cache_clear()
    yield tmp_path
    brand.data_uri.cache_clear()


def _picture(path: Path, size: tuple[int, int], color: tuple[int, ...]) -> None:
    Image.new("RGBA", size, color).save(path)


async def test_nothing_is_shown_without_the_pictures(pictures: Path) -> None:
    assert brand.logo_mark() is None and brand.seal(True, "#ffffff") is None and brand.avatar_jpeg() is None
    page = _environment().get_template("verify.html").render(heading="Topilmadi", rows=[], valid=False, club="Klub")
    assert "<img" not in page


async def test_the_clubs_pictures_fill_their_places(db: AsyncSession, pictures: Path) -> None:
    _picture(pictures / "logo-mark.png", (2000, 2000), (20, 69, 47, 255))
    _picture(pictures / "seal.png", (1200, 1200), (30, 58, 138, 200))
    _picture(pictures / "seal-light.png", (1200, 1200), (201, 162, 78, 200))
    Image.new("RGB", (900, 700), (20, 69, 47)).save(pictures / "bot-avatar.jpg")

    assert brand.logo_mark() is not None and brand.logo_mark().startswith("data:image/png;base64,")
    # A dark design gets the light seal; without it the ordinary one.
    assert brand.seal(True, "#181a1f") == brand.data_uri("seal-light", 600)
    assert brand.seal(True, "#fffdf7") == brand.data_uri("seal", 600)
    assert brand.seal(False, "#fffdf7") is None
    avatar = brand.avatar_jpeg()
    assert avatar is not None and avatar[:2] == b"\xff\xd8"
    with Image.open(__import__("io").BytesIO(avatar)) as image:
        assert image.size == (640, 640)  # squared for Telegram

    owner = await create_user(db)
    await db.commit()
    values = await certificates._brand_values(db, "#fffdf7")
    assert values["seal"] and values["logo"]
    await update_setting(db, key="certificates.seal", value=False, actor_id=owner.id)
    await update_setting(db, key="certificates.logo", value=False, actor_id=owner.id)
    assert await certificates._brand_values(db, "#fffdf7") == {"seal": None, "logo": None}

    page = _environment().get_template("verify.html").render(heading="Haqiqiy", rows=[], valid=True, club="Klub")
    assert 'class="brand"' in page and "data:image/png;base64," in page
