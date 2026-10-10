"""The admin panel's search box: members, books, events, tests, rewards, settings, pages and bot commands
in one list (e.g. «stiker» finds the channel stickers, the setting and the /stiker command)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, Event, Reward, Test, User
from app.services.settings import SETTING_DEFINITIONS

_APOSTROPHES = re.compile(r"[ʻʼ’‘`´]")

# (title, admin route, keywords, permission or None)
PLACES: tuple[tuple[str, str, str, str | None], ...] = (
    ("👥 A'zolar", "members", "azo a'zolar talaba foydalanuvchi ro'yxat bloklash", "USER_VIEW"),
    ("📚 Kitoblar", "books", "kitob muqova muddat o'quvchi", "BOOK_VIEW"),
    ("💬 Iqtiboslar", "quotes", "iqtibos kun iqtibosi qoralama rejalashtirilgan arxiv", "BOOK_VIEW"),
    ("📅 Tadbirlar va davomat", "events", "tadbir davomat smena qr kod ro'yxatdan o'tish fikr reyting", "EVENT_VIEW"),
    ("📝 Testlar", "tests", "test savol import fayl word pdf rasm natija", "TEST_VIEW"),
    ("🏆 Ballar va reyting", "scores", "ball reyting mavsum o'quv yili", "SCORE_VIEW"),
    ("📄 Hisobotlar", "reports", "hisobot tadbir hisoboti pdf rasm", "REPORT_VIEW"),
    ("🗂 Hujjatlar", "documents", "hujjat excel word pdf eksport yuklab olish statistika qr talabalar", None),
    ("🏅 Yutuqlar", "achievements", "yutuq nishon chegara tartib", None),
    ("🎁 Sovg'alar", "rewards", "sovg'a promokod kod tarqatish", "REWARD_MANAGE"),
    ("🎲 Sovg'a o'yinlari", "giveaways", "o'yin giveaway random", "REWARD_MANAGE"),
    ("🎓 Sertifikatlar", "certificates", "sertifikat dizayn fon rasm", "REWARD_MANAGE"),
    ("📨 Murojaatlar", "support", "murojaat savol yordam adminga yozish", "SUPPORT_MANAGE"),
    ("📢 Xabarlar", "notifications", "xabar e'lon broadcast tugma yuborish", "NOTIFICATION_SEND"),
    ("📣 Telegram kanal", "channel", "kanal post stiker sticker tekshiruv", "NOTIFICATION_SEND"),
    ("🏛 Fakultetlar", "faculties", "fakultet", None),
    ("⚙️ Sozlamalar", "settings", "sozlama ball vaqt karta obuna", None),
    ("🧩 Imkoniyatlar", "features", "imkoniyat funksiya yoqish o'chirish premium", "SUPER_ADMIN"),
    ("💎 Premium va to'lovlar", "premium", "premium to'lov karta chek stars tarif qaytarish", "SUPER_ADMIN"),
    ("🛡 Adminlar", "admins", "admin rol ruxsat", "SUPER_ADMIN"),
    ("🧾 Audit jurnali", "audit", "audit jurnal kim nima qildi", "AUDIT_LOG_VIEW"),
)

# Bot commands (shown with an explanation; no page to open).
COMMANDS: tuple[tuple[str, str], ...] = (
    ("/stiker", "Botga stikerlarni yuborib, kanal postlari va tabriklar uchun saqlash (adminlar)"),
    ("/emoji", "Premium emojilarni o'rgatish: bot xabarlaridagi oddiy emojilar premiumga almashadi (adminlar)"),
    ("/admin", "Boshqaruv: qisqa holat va admin panel"),
    ("/davomat", "Tadbirda davomat qilish"),
    ("/pasport", "Kitobxon pasporti"),
    ("/premium", "Premium va klubni qo'llab-quvvatlash"),
    ("/taklif", "Do'stni klubga taklif qilish"),
    ("/help", "Yordam, savol-javoblar va adminga yozish"),
    ("/paysupport", "To'lov bo'yicha yordam"),
    ("/cancel", "Joriy amalni bekor qilish"),
    ("/stop", "Hamma jarayonni to'xtatish va menyuga qaytish"),
    ("/myid", "Telegram ID ni bilish"),
    ("/terms", "To'lov shartlari"),
)


def normalize(text: str) -> str:
    return _APOSTROPHES.sub("'", text).strip().lower()


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def search(session: AsyncSession, query: str, *, permissions: set[str], roles: set[str]) -> list[dict[str, Any]]:
    """Up to ~40 results, the most useful kinds first."""
    from app.services.passport import member_number

    q = normalize(query)
    if len(q) < 2:
        return []
    allowed = permissions | roles
    pattern = _like(q)
    results: list[dict[str, Any]] = []

    if "USER_VIEW" in allowed:
        digits = re.sub(r"\D", "", q)
        conditions = [
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
            (User.last_name + " " + User.first_name).ilike(pattern),
            (User.first_name + " " + User.last_name).ilike(pattern),
            User.group_name.ilike(pattern),
            User.telegram_username.ilike(_like(q.lstrip("@"))),
        ]
        if len(digits) >= 3:
            conditions.append(User.phone.like(_like(digits)))
            conditions.append(User.member_number == int(digits[-9:]))
        for user in await session.scalars(
            select(User).where(User.deleted_at.is_(None), or_(*conditions)).order_by(User.last_name).limit(8)
        ):
            results.append(
                {
                    "kind": "member",
                    "title": f"{user.last_name} {user.first_name}",
                    "subtitle": " · ".join(
                        part for part in (member_number(user), user.group_name, str(user.status).lower()) if part
                    ),
                    "route": f"members?q={user.last_name}",
                }
            )
    if "BOOK_VIEW" in allowed:
        for book in await session.scalars(
            select(Book)
            .where(Book.deleted_at.is_(None), or_(Book.title.ilike(pattern), Book.author.ilike(pattern)))
            .limit(5)
        ):
            results.append({"kind": "book", "title": book.title, "subtitle": book.author, "route": "books"})
    if "EVENT_VIEW" in allowed:
        for event in await session.scalars(
            select(Event)
            .where(Event.deleted_at.is_(None), Event.title.ilike(pattern))
            .order_by(Event.starts_at.desc())
            .limit(5)
        ):
            from app.utils.timezone import format_datetime

            results.append(
                {
                    "kind": "event",
                    "title": event.title,
                    "subtitle": format_datetime(event.starts_at),
                    "route": f"events/{event.id}/attendance",
                }
            )
    if "TEST_VIEW" in allowed:
        for test in await session.scalars(
            select(Test).where(Test.deleted_at.is_(None), Test.title.ilike(pattern)).limit(5)
        ):
            results.append(
                {"kind": "test", "title": test.title, "subtitle": str(test.status), "route": f"tests/{test.id}"}
            )
    if "REWARD_MANAGE" in allowed:
        for reward in await session.scalars(select(Reward).where(Reward.title.ilike(pattern)).limit(5)):
            results.append({"kind": "reward", "title": reward.title, "subtitle": "Sovg'a", "route": "rewards"})

    for title, route, keywords, permission in PLACES:
        if permission is not None and permission not in allowed and "SUPER_ADMIN" not in roles:
            continue
        if q in normalize(title) or q in keywords:
            results.append({"kind": "page", "title": title, "subtitle": "Bo'lim", "route": route})
    for definition in SETTING_DEFINITIONS:
        if q in definition.key.lower() or q in normalize(definition.description):
            results.append(
                {
                    "kind": "setting",
                    "title": definition.description[:90],
                    "subtitle": f"Sozlama: {definition.key}",
                    "route": f"settings?key={definition.key}",
                }
            )
    for command, description in COMMANDS:
        if q.lstrip("/") in command or q in normalize(description):
            results.append({"kind": "command", "title": command, "subtitle": f"Botda: {description}", "route": None})
    return results[:40]
