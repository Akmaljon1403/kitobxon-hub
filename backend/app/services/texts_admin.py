"""«📝 Matnlar» — every word the bot says, editable by the owner in the Admin Panel, with no programmer and
no access to the server.

Three kinds of text are listed:

* ``bot`` — the bot's own messages (``app/bot/texts.py``), grouped as in that file;
* ``notify`` — the notifications members receive (event reminders, new books, test results, …);
* ``channel`` — the phrase lists the channel posts are made of (new book, reading reminders, invites).

An edit is one or several variants (sent in turn, so members do not read the same sentence every time), is
checked before it is saved (only the ``{placeholders}`` the message really has, only Telegram's HTML), is
written to the audit log with who and when, and can be reset to the built-in wording at any moment. Button
captions are not edited here: the bot recognises its menu by them.
"""

from __future__ import annotations

import html
import re
import string
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import text_store
from app.core.errors import BadRequestError, ForbiddenError, NotFoundError
from app.models import NotificationTemplate, TextOverride, User
from app.services.audit import record_audit

MAX_VARIANTS = 10
MAX_LENGTH = 4000
ALLOWED_TAGS = {
    "b",
    "strong",
    "i",
    "em",
    "u",
    "ins",
    "s",
    "strike",
    "del",
    "a",
    "code",
    "pre",
    "blockquote",
    "tg-spoiler",
    "span",
    "tg-emoji",
}

# The sections of texts.py (English notes for programmers) as the owner sees them.
SECTIONS: dict[str, str] = {
    "Registration": "📝 Ro'yxatdan o'tish",
    "Required channel subscription": "📢 Majburiy obuna",
    "Registered members": "👋 Salomlashish va hisob holati",
    "Section summaries (short; details are in the Mini App)": "📋 Menyu bo'limlari javoblari",
    "Help and messages to the club": "💬 Yordam va murojaatlar",
    "Administrators": "🛠 Adminlar uchun xabarlar",
    "Misc": "⚙️ Umumiy javoblar",
    "Feature switches": "🔒 Yopiq va Premium bo'limlar",
    "Premium and donations (Telegram Stars)": "💎 Premium va hissa",
    "Event feedback": "⭐ Tadbir bahosi",
    "Card payments": "💳 Karta orqali to'lov",
    "Card payments: the super admin's side": "💳 To'lovlar — adminlar tomoni",
    "Channel stickers (/stiker, admins)": "🎨 Stikerlar",
    "Channel posts: the admins look first": "📣 Kanal postlarini ko'rib chiqish",
    "Portfolio": "🗂 Portfolio",
    "Leaving and coming back": "🚪 Klubdan chiqish va qaytish",
    "Events and books opened from the channel": "🔗 Kanaldan ochilgan tadbir va kitoblar",
    "Channels and groups the bot is added to": "📡 Kanal va guruhlar",
    "My reading: /oqidim, /javonim, /kartam": "📚 Mening mutolaam",
    "«💬 A'zolar fikrlari» (/fikr)": "💬 A'zolar fikrlari",
    "Answers in the payments channel («Reply»)": "↩️ To'lovlar kanalida javob",
    "«What is this channel's id?» (an admin forwards a channel post)": "🆔 Kanal ID",
}
SKIPPED_SECTIONS = {"Main menu (the same names are used in the Mini App)", "Inline buttons", "Live wording"}

# Example values for «📤 Menga botda ko'rsatish» — the owner sees how the message will look.
SAMPLES: dict[str, str] = {
    "first_name": "Akmaljon",
    "last_name": "Bahodirov",
    "name": "Akmaljon Bahodirov",
    "title": "O'tkan kunlar",
    "event_title": "«O'tkan kunlar» muhokamasi",
    "book_title": "O'tkan kunlar",
    "book_author": "Abdulla Qodiriy",
    "author": "Abdulla Qodiriy",
    "test_title": "O'tkan kunlar bo'yicha test",
    "quote_text": "Kitob — eng sodiq do'st",
    "quote_author": "Xalq maqoli",
    "starts_at": "25-oktabr, 15:00",
    "ends_at": "27-oktabr, 23:59",
    "deadline": "30-oktabr",
    "location": "Kutubxona, 2-qavat",
    "points": "30",
    "score": "18",
    "max_score": "20",
    "rank": "3",
    "total": "245",
    "members": "1 250",
    "days": "3",
    "step": "1",
    "count": "2",
    "minutes": "15",
    "duration": "20",
    "message": "Bu yerda xabar matni bo'ladi.",
}


class _HtmlCheck(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.problems: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            self.problems.append(f"<{tag}> tegi Telegram'da ishlamaydi")
            return
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in ALLOWED_TAGS:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"</{tag}> yopilishi noto'g'ri joyda")
            return
        self.stack.pop()


def placeholders(text: str) -> set[str]:
    """The ``{names}`` a text uses (raises ValueError for a stray brace)."""
    names = set()
    for _, field, spec, conversion in string.Formatter().parse(text):
        if field is None:
            continue
        if not field.isidentifier() or spec or conversion:
            raise ValueError(field)
        names.add(field)
    return names


def check(text: str, allowed: set[str], *, braces: bool) -> list[str]:
    """What is wrong with one variant (empty — it is fine)."""
    problems = []
    if not text.strip():
        return ["Matn bo'sh"]
    if len(text) > MAX_LENGTH:
        problems.append(f"Juda uzun: {len(text)} belgi (ko'pi bilan {MAX_LENGTH})")
    if braces:
        try:
            used = placeholders(text)
        except ValueError:
            problems.append("Jingalak qavs { } noto'g'ri: faqat {nomi} ko'rinishida, ro'yxatdagilarni ishlating")
        else:
            unknown = sorted(used - allowed)
            if unknown:
                known = ", ".join("{" + name + "}" for name in sorted(allowed)) or "yo'q"
                problems.append(
                    "Noma'lum o'rinbosar: "
                    + ", ".join("{" + name + "}" for name in unknown)
                    + f". Bu xabarda bor: {known}"
                )
    elif "{" in text or "}" in text:
        problems.append("Bu xabarda o'rinbosar yo'q — { } belgilarini ishlatmang")
    checker = _HtmlCheck()
    try:
        checker.feed(text)
        checker.close()
    except Exception:  # pragma: no cover - HTMLParser is forgiving
        problems.append("HTML noto'g'ri")
    problems.extend(checker.problems)
    if checker.stack:
        problems.append("Yopilmagan teg: " + ", ".join(f"<{tag}>" for tag in checker.stack))
    return problems


# ---------------------------------------------------------------------------- the catalogue


def _bot_texts() -> list[dict[str, Any]]:
    from app.bot import texts

    source = Path(texts.__file__).read_text(encoding="utf-8")
    values = texts.__dict__
    items = []
    section = ""
    for line in source.splitlines():
        header = re.match(r"^# ---- (.+?) -+$", line)
        if header:
            section = header.group(1).strip()
            continue
        match = re.match(r"^([A-Z][A-Z0-9_]*) = ", line)
        if not match or section in SKIPPED_SECTIONS:
            continue
        key = match.group(1)
        value = values.get(key)
        if type(value) is not str or key.startswith(texts.FIXED_PREFIXES):
            continue
        items.append(
            {
                "key": key,
                "kind": "bot",
                "group": SECTIONS.get(section, "⚙️ Boshqa"),
                "title": _title(value),
                "default": value,
                "builtin": list(text_store.builtin(key)),
                "allowed": sorted(_safe_placeholders(value)),
                "braces": bool(_safe_placeholders(value)),
            }
        )
    return items


def _safe_placeholders(text: str) -> set[str]:
    try:
        return placeholders(text)
    except ValueError:
        return set()


def _title(text: str) -> str:
    """The first line without HTML: what the owner recognises the message by."""
    plain = re.sub(r"<[^>]+>", "", text).strip().splitlines()
    first = plain[0] if plain else text
    return html.unescape(first)[:90]


def _notify_texts(templates: dict[str, NotificationTemplate]) -> list[dict[str, Any]]:
    from app.services.defaults import DEFAULT_NOTIFICATION_TEMPLATES

    items = []
    for seed in DEFAULT_NOTIFICATION_TEMPLATES:
        code = seed.type.value
        row = templates.get(code)
        default = row.body if row is not None else seed.body
        names = _safe_placeholders(default)
        items.append(
            {
                "key": f"notify.{code}",
                "kind": "notify",
                "group": "🔔 A'zolarga bildirishnomalar",
                "title": seed.title,
                "default": default,
                "builtin": list(text_store.builtin(f"notify.{code}")),
                "allowed": sorted(names),
                "braces": True,  # templates are always filled in
                "active": row.is_active if row is not None else True,
            }
        )
    return items


def _channel_texts() -> list[dict[str, Any]]:
    from app.services import channel

    items = []
    for key, (title, phrases, hint) in channel.EDITABLE.items():
        names: set[str] = set()
        for phrase in phrases:
            names |= _safe_placeholders(phrase)
        items.append(
            {
                "key": key,
                "kind": "channel",
                "group": "📣 Kanal postlari",
                "title": title,
                "default": phrases[0],
                "defaults": list(phrases),
                "builtin": list(phrases[1:]),
                "allowed": sorted(names),
                "braces": bool(names),
                "hint": hint,
            }
        )
    return items


async def catalogue(session: AsyncSession) -> list[dict[str, Any]]:
    """Everything editable, with the owner's edits and who made them."""
    templates = {row.type.value: row for row in await session.scalars(select(NotificationTemplate))}
    edits = {row.key: row for row in await session.scalars(select(TextOverride))}
    names = {}
    editors = {row.updated_by for row in edits.values() if row.updated_by}
    if editors:
        names = {
            user.id: f"{user.first_name} {user.last_name or ''}".strip()
            for user in await session.scalars(select(User).where(User.id.in_(editors)))
        }
    items = [*_bot_texts(), *_notify_texts(templates), *_channel_texts()]
    for item in items:
        edit = edits.get(item["key"])
        item["variants"] = list(edit.variants) if edit else None
        item["rotate"] = edit.rotate if edit else True
        item["updated_at"] = edit.updated_at if edit else None
        item["updated_by"] = names.get(edit.updated_by) if edit and edit.updated_by else None
        item.setdefault("active", None)
        item.setdefault("hint", None)
        item.setdefault("defaults", None)
    return items


def _find(key: str) -> dict[str, Any]:
    for item in [*_bot_texts(), *_notify_texts({}), *_channel_texts()]:
        if item["key"] == key:
            return item
    raise NotFoundError("TEXT_NOT_FOUND", "Bunday matn topilmadi.")


def validate(key: str, variants: list[str]) -> tuple[dict[str, Any], list[str]]:
    """The cleaned variants of an edit, or a clear error for the first problem."""
    item = _find(key)
    clean = [variant.replace("\r\n", "\n").strip() for variant in variants]
    clean = [variant for variant in clean if variant]
    if not clean:
        raise BadRequestError("TEXT_EMPTY", "Kamida bitta variant yozing (yoki «Asl holiga qaytarish»ni bosing).")
    if len(clean) > MAX_VARIANTS:
        raise BadRequestError("TOO_MANY_VARIANTS", f"Ko'pi bilan {MAX_VARIANTS} ta variant.")
    allowed = set(item["allowed"])
    for number, variant in enumerate(clean, start=1):
        problems = check(variant, allowed, braces=item["braces"])
        if problems:
            raise BadRequestError(
                "TEXT_INVALID", f"{number}-variant: " + "; ".join(problems), details={"variant": number}
            )
    return item, clean


MONEY_GROUPS = ("💳", "💎")
MONEY_KEYS = ("CARD_", "PAY", "PREMIUM", "DONAT", "STARS")


def money_text(key: str) -> bool:
    """Texts about payments (card numbers, prices, how to pay): only the super admins rewrite them — a changed
    instruction could send members' money elsewhere."""
    if key.startswith(MONEY_KEYS):
        return True
    item = next((item for item in _bot_texts() if item["key"] == key), None)
    return bool(item and item["group"].startswith(MONEY_GROUPS))


async def save(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    key: str,
    variants: list[str],
    rotate: bool = True,
    super_admin: bool = True,
) -> None:
    if money_text(key) and not super_admin:
        raise ForbiddenError("OWNER_ONLY_TEXT", "To'lovga oid matnlarni faqat bosh admin o'zgartiradi.")
    _, clean = validate(key, variants)
    before = await session.get(TextOverride, key)
    previous = list(before.variants) if before else None
    statement = insert(TextOverride).values(key=key, variants=clean, rotate=rotate, updated_by=actor_id)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[TextOverride.key],
            set_={"variants": clean, "rotate": rotate, "updated_by": actor_id, "updated_at": func.now()},
        )
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="TEXT_EDIT",
        entity_type="text",
        before={"key": key, "variants": previous},
        after={"key": key, "variants": clean, "rotate": rotate},
    )
    if not super_admin:  # the owners see every change of the bot's words made by someone else
        from app.services import security_alerts

        await security_alerts.rights_changed(
            session, actor_id=actor_id, user_id=actor_id, what=f"bot matnini o'zgartirdi: {key}"
        )
    await session.commit()
    await text_store.refresh(session, force=True)


async def reset(session: AsyncSession, *, actor_id: uuid.UUID, key: str) -> None:
    _find(key)
    edit = await session.get(TextOverride, key)
    if edit is None:
        return
    record_audit(
        session,
        actor_id=actor_id,
        action="TEXT_RESET",
        entity_type="text",
        before={"key": key, "variants": list(edit.variants)},
    )
    await session.execute(delete(TextOverride).where(TextOverride.key == key))
    await session.commit()
    await text_store.refresh(session, force=True)


async def set_active(session: AsyncSession, *, actor_id: uuid.UUID, key: str, active: bool) -> None:
    """A member notification switched on or off (e.g. no «🏆 reyting» messages at all)."""
    if not key.startswith("notify."):
        raise BadRequestError("NOT_A_NOTIFICATION", "Faqat bildirishnomalarni o'chirish mumkin.")
    template = await session.scalar(
        select(NotificationTemplate).where(NotificationTemplate.type == key.removeprefix("notify."))
    )
    if template is None:
        raise NotFoundError("TEXT_NOT_FOUND", "Bunday bildirishnoma topilmadi.")
    template.is_active = active
    template.updated_by = actor_id
    record_audit(
        session,
        actor_id=actor_id,
        action="NOTIFICATION_TEMPLATE_SWITCH",
        entity_type="text",
        after={"key": key, "active": active},
    )
    await session.commit()


def sample(text: str) -> str:
    """The message with example values in place of ``{placeholders}``."""
    try:
        names = placeholders(text)
    except ValueError:
        return text
    values = {name: html.escape(SAMPLES.get(name, f"[{name}]"), quote=False) for name in names}
    return text.format_map(values) if names else text


async def export(session: AsyncSession) -> dict[str, Any]:
    rows = await session.scalars(select(TextOverride).order_by(TextOverride.key))
    return {"version": 1, "texts": {row.key: {"variants": list(row.variants), "rotate": row.rotate} for row in rows}}


async def import_(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    """A saved copy back (e.g. from another server): every text is checked; nothing is saved if one fails."""
    texts = data.get("texts")
    if not isinstance(texts, dict) or not texts:
        raise BadRequestError("IMPORT_EMPTY", "Faylda matnlar topilmadi.")
    checked = []
    for key, value in texts.items():
        if not isinstance(value, dict) or not isinstance(value.get("variants"), list):
            raise BadRequestError("IMPORT_INVALID", f"«{key}»: variantlar ro'yxati yo'q.")
        try:
            _, clean = validate(str(key), [str(variant) for variant in value["variants"]])
        except NotFoundError:
            continue  # a text this version no longer has
        except BadRequestError as exc:
            raise BadRequestError("IMPORT_INVALID", f"«{key}» — {exc.message}") from None
        checked.append((str(key), clean, bool(value.get("rotate", True))))
    for key, clean, rotate in checked:
        statement = insert(TextOverride).values(key=key, variants=clean, rotate=rotate, updated_by=actor_id)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[TextOverride.key],
                set_={"variants": clean, "rotate": rotate, "updated_by": actor_id, "updated_at": func.now()},
            )
        )
    record_audit(session, actor_id=actor_id, action="TEXT_IMPORT", entity_type="text", after={"count": len(checked)})
    await session.commit()
    await text_store.refresh(session, force=True)
    return {"imported": len(checked)}
