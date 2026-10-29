"""Feature switches: the super admin decides who may use each bot feature.

* ``OFF`` — nobody (the button is hidden, the API answers 403 ``FEATURE_OFF``);
* ``ALL`` — every member;
* ``PREMIUM`` — premium members only (others see a 💎 lock and an invitation to Premium).

Turning a feature on can announce it to members: "Tabriklaymiz, bot yangilandi! ...".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, BadRequestError, NotFoundError
from app.models import FeatureFlag, User
from app.models.enums import FeatureMode, NotificationType
from app.services.audit import record_audit
from app.services.notifications import active_members, enqueue_for_members, render

Access = Literal["on", "premium", "off"]


@dataclass(frozen=True)
class Feature:
    code: str
    title: str
    description: str  # what the member gets; used in the announcement
    default: FeatureMode
    route: str | None = None  # Mini App page opened from the announcement
    premium_allowed: bool = True  # the store itself cannot be "premium only"


FEATURES: tuple[Feature, ...] = (
    Feature(
        "passport",
        "🪪 Kitobxon pasporti",
        "rasmli a'zolik pasporti — yuklab olish va do'stlarga ulashish mumkin",
        FeatureMode.ALL,
        "profile",
    ),
    Feature(
        "certificates",
        "🎓 Sertifikatlar",
        "g'oliblik sertifikatlari — QR kod orqali istalgan kishi haqiqiyligini tekshira oladi",
        FeatureMode.ALL,
        "certificates",
    ),
    Feature(
        "certificate_pdf",
        "📄 Sertifikat PDF",
        "sertifikatni PDF shaklida cheksiz yuklab olish va 12 ta dizayndan birini tanlash",
        FeatureMode.PREMIUM,
        "certificates",
    ),
    Feature("ranking", "🏆 Reyting", "haftalik klub reytingi", FeatureMode.ALL, "ranking"),
    Feature(
        "ranking_full",
        "🏆 To'liq reyting",
        "oylik va umumiy reyting, fakultetim, guruhim va fakultetlar bellashuvi",
        FeatureMode.PREMIUM,
        "ranking",
    ),
    Feature("achievements", "🏅 Yutuqlar", "nishonlar va ularga yetish yo'li", FeatureMode.ALL, "achievements"),
    Feature("rewards", "🎁 Sovg'alar", "sovg'alar va promo-kodlar", FeatureMode.ALL, "rewards"),
    Feature("support", "💬 Adminga yozish", "klub rahbariyatiga savol va taklif yuborish", FeatureMode.ALL),
    Feature("quote_of_day", "📜 Kun iqtibosi", "har kuni klub kitoblaridan tanlangan iqtibos", FeatureMode.ALL),
    Feature(
        "event_feedback",
        "⭐ Tadbirga baho",
        "tadbirdan keyin unga baho berish va fikr qoldirish",
        FeatureMode.ALL,
        "events",
    ),
    Feature(
        "weekly_digest",
        "📊 Haftalik xulosa",
        "har dushanba shaxsiy xulosa: haftalik ballar, reytingdagi o'rin va keyingi tadbirlar",
        FeatureMode.PREMIUM,
        "results",
    ),
    Feature(
        "personal_stats",
        "📈 Shaxsiy statistika",
        "oylar bo'yicha ballaringiz, davomat foizi, test natijalari va reytingdagi o'sishingiz",
        FeatureMode.PREMIUM,
        "stats",
    ),
    Feature(
        "portfolio",
        "🗂 Kitobxonlik portfoliosi",
        "barcha natija, sertifikat va yutuqlaringiz bitta chiroyli PDF hujjatda — rezyume va grantlar uchun",
        FeatureMode.PREMIUM,
        "profile",
    ),
    Feature(
        "shelf",
        "📚 Javonim va mutolaa kundaligi",
        "shaxsiy kitob javoni (o'qimoqchiman / o'qiyapman / o'qidim / keyinroq), kunlik betlar kundaligi, "
        "ketma-ket o'qish seriyasi va kitobdan keyin 3 savol",
        FeatureMode.ALL,
        "shelf",
    ),
    Feature(
        "missions",
        "🎯 Shaxsiy missiyalar",
        "«7 kunda 100 bet», «5 kun ketma-ket o'qish» kabi kichik maqsadlar — bajarganga ball",
        FeatureMode.ALL,
        "missions",
    ),
    Feature(
        "reading_card",
        "🪪 Kitobxonlik kartam",
        "o'qigan kitoblar, betlar, seriya va yutuqlaringiz bitta chiroyli rasmda — ulashish uchun",
        FeatureMode.ALL,
        "card",
    ),
    Feature(
        "faculty_league",
        "🏛 Fakultetlar ligasi",
        "fakultetlar bellashuvi: o'rtacha ball, faol kitobxonlar ulushi, o'qilgan betlar va kitoblar",
        FeatureMode.ALL,
        "league",
    ),
    Feature(
        "community",
        "💬 A'zolar fikrlari",
        "kitobdan iqtiboslar, o'z fikrlaringiz, kitob va tadbir taassurotlari, klub haqidagi e'tiroflar — "
        "yuborish, boshqalarnikini o'qish, ❤️ bosish va chiroyli kartochka qilib ulashish",
        FeatureMode.ALL,
        "community",
    ),
    Feature(
        "premium",
        "💎 Premium obuna",
        "Premium a'zolik: qo'shimcha imkoniyatlar, oltin pasport va klub rivojiga hissa",
        FeatureMode.OFF,
        "premium",
        premium_allowed=False,
    ),
    Feature(
        "card_payments",
        "💳 Karta orqali to'lov",
        "Premiumni bank kartasiga o'tkazib, chekni yuborish orqali sotib olish",
        FeatureMode.OFF,
        "premium",
        premium_allowed=False,
    ),
    Feature(
        "donations",
        "❤️ Klubni qo'llab-quvvatlash",
        "Telegram Stars orqali klub rivojiga hissa qo'shish",
        FeatureMode.OFF,
        "premium",
        premium_allowed=False,
    ),
)
FEATURES_BY_CODE = {feature.code: feature for feature in FEATURES}


class FeatureOffError(AppError):
    status_code = 403

    def __init__(self, feature: Feature) -> None:
        super().__init__("FEATURE_OFF", f"«{feature.title}» hozircha o'chirilgan.")


class PremiumRequiredError(AppError):
    status_code = 403

    def __init__(self, feature: Feature) -> None:
        super().__init__(
            "PREMIUM_REQUIRED", f"«{feature.title}» — Premium a'zolar uchun imkoniyat. 💎 Premium bo'limini oching."
        )


def get_feature(code: str) -> Feature:
    try:
        return FEATURES_BY_CODE[code]
    except KeyError as exc:
        raise NotFoundError("FEATURE_NOT_FOUND", "Bunday imkoniyat yo'q.") from exc


async def modes(session: AsyncSession) -> dict[str, FeatureMode]:
    stored = {row.code: row.mode for row in await session.scalars(select(FeatureFlag))}
    return {feature.code: FeatureMode(stored.get(feature.code, feature.default)) for feature in FEATURES}


async def mode(session: AsyncSession, code: str) -> FeatureMode:
    feature = get_feature(code)
    stored = await session.scalar(select(FeatureFlag.mode).where(FeatureFlag.code == code))
    return FeatureMode(stored or feature.default)


async def access(session: AsyncSession, user: User) -> dict[str, Access]:
    """What the member may use: "on", "premium" (locked: needs Premium) or "off"."""
    from app.services.premium import is_premium

    current = await modes(session)
    premium = None
    result: dict[str, Access] = {}
    for code, value in current.items():
        if value == FeatureMode.ALL:
            result[code] = "on"
        elif value == FeatureMode.OFF:
            result[code] = "off"
        else:
            if premium is None:
                premium = await is_premium(session, user.id)
            result[code] = "on" if premium else "premium"
    return result


async def allowed(session: AsyncSession, user: User, code: str) -> Access:
    from app.services.premium import is_premium

    value = await mode(session, code)
    if value == FeatureMode.ALL:
        return "on"
    if value == FeatureMode.OFF:
        return "off"
    return "on" if await is_premium(session, user.id) else "premium"


async def require(session: AsyncSession, user: User, code: str) -> None:
    """Raise a friendly 403 unless the member may use the feature."""
    state = await allowed(session, user, code)
    if state == "off":
        raise FeatureOffError(get_feature(code))
    if state == "premium":
        raise PremiumRequiredError(get_feature(code))


async def recipients(session: AsyncSession, code: str) -> Select[tuple[uuid.UUID]] | None:
    """Members who receive a feature's messages (e.g. the daily quote); None when it is off."""
    from app.services.premium import premium_members

    value = await mode(session, code)
    if value == FeatureMode.OFF:
        return None
    return active_members() if value == FeatureMode.ALL else premium_members()


async def set_mode(
    session: AsyncSession, *, actor_id: uuid.UUID, code: str, new_mode: FeatureMode, announce: bool
) -> int:
    """Change who may use a feature. Returns how many members were told about it."""
    feature = get_feature(code)
    if new_mode == FeatureMode.PREMIUM and not feature.premium_allowed:
        raise BadRequestError("FEATURE_NOT_PREMIUM", "Bu bo'limni faqat yoqish yoki o'chirish mumkin.")
    old_mode = await mode(session, code)
    statement = insert(FeatureFlag).values(code=code, mode=new_mode, updated_by=actor_id)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[FeatureFlag.code], set_={"mode": new_mode, "updated_by": actor_id, "updated_at": func.now()}
        )
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="FEATURE_MODE",
        entity_type="feature",
        entity_id=code,
        before={"mode": str(old_mode)},
        after={"mode": str(new_mode), "announce": announce},
    )
    told = 0
    if announce and new_mode != old_mode and new_mode != FeatureMode.OFF:
        told = await _announce(session, feature, old_mode, new_mode)
    await session.commit()
    return told


async def _announce(session: AsyncSession, feature: Feature, old_mode: FeatureMode, new_mode: FeatureMode) -> int:
    from app.services.premium import non_premium_members, premium_members

    batch = uuid.uuid4().hex[:8]  # a later announcement of the same feature is a new message
    button = {"buttons": [{"text": "📱 Ko'rish", "app_route": feature.route or ""}]}
    if new_mode == FeatureMode.ALL:
        # From premium-only to everyone: premium members already had it.
        members = non_premium_members() if old_mode == FeatureMode.PREMIUM else active_members()
        text = await render(
            session, NotificationType.ANNOUNCEMENT, title=feature.title, description=feature.description
        )
        if text is None:
            return 0
        return await enqueue_for_members(
            session,
            type_=NotificationType.ANNOUNCEMENT,
            text=text,
            dedup_prefix=f"feature:{feature.code}:{batch}",
            members=members,
            payload=button,
        )
    # Premium only: premium members get it now, the others learn what Premium adds.
    text = await render(session, NotificationType.ANNOUNCEMENT, title=feature.title, description=feature.description)
    told = 0
    if text is not None:
        told += await enqueue_for_members(
            session,
            type_=NotificationType.ANNOUNCEMENT,
            text=text,
            dedup_prefix=f"feature:{feature.code}:{batch}",
            members=premium_members(),
            payload=button,
        )
    if await mode(session, "premium") != FeatureMode.OFF:
        teaser = (
            f"💎 <b>Premium a'zolar uchun yangi imkoniyat</b>\n\n{feature.title} — {feature.description}.\n\n"
            "Premium obuna klub rivojiga ham hissa bo'ladi."
        )
        told += await enqueue_for_members(
            session,
            type_=NotificationType.ANNOUNCEMENT,
            text=teaser,
            dedup_prefix=f"feature:{feature.code}:{batch}:teaser",
            members=non_premium_members(),
            payload={"buttons": [{"text": "💎 Premium haqida", "app_route": "premium"}]},
        )
    return told
