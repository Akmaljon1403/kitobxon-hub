"""Reply and inline keyboards."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)

from app.bot import texts
from app.core.config import get_settings
from app.models import Faculty, UserNotificationSettings

# Mini App pages (hash routes) behind each menu section.
SECTION_ROUTES = {
    texts.BTN_BOOKS: "books",
    texts.BTN_EVENTS: "events",
    texts.BTN_ATTENDANCE: "checkin",
    texts.BTN_TESTS: "tests",
    texts.BTN_RESULTS: "results",
    texts.BTN_RANKING: "ranking",
    texts.BTN_PASSPORT: "profile",
    texts.BTN_ACHIEVEMENTS: "achievements",
}

MEMBER_ROWS = (
    (texts.BTN_BOOKS, texts.BTN_EVENTS),
    (texts.BTN_ATTENDANCE, texts.BTN_TESTS),
    (texts.BTN_RESULTS, texts.BTN_RANKING),
    (texts.BTN_PASSPORT, texts.BTN_ACHIEVEMENTS),
    (texts.BTN_SETTINGS, texts.BTN_HELP),
)
MENU_BUTTONS = frozenset(label for row in MEMBER_ROWS for label in row) | {texts.BTN_ADMIN}


def main_menu(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [list(row) for row in MEMBER_ROWS]
    if is_admin:
        rows.append([texts.BTN_ADMIN])
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Bo'limni tanlang",
    )


def remove() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def share_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.BTN_SHARE_PHONE, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def faculties(items: list[Faculty]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=item.name, callback_data=f"reg:fac:{item.id}")] for item in items]
    )


def courses(max_course: int) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{n}-kurs", callback_data=f"reg:course:{n}") for n in range(1, max_course + 1)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i : i + 3] for i in range(0, len(buttons), 3)])


def confirm_registration() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.BTN_CONFIRM, callback_data="reg:confirm")],
            [InlineKeyboardButton(text=texts.BTN_RESTART, callback_data="reg:restart")],
        ]
    )


def app_button(route: str = "", text: str = texts.BTN_OPEN_APP) -> InlineKeyboardButton | None:
    """WebApp button for a Mini App page. Mini Apps opened from inline buttons receive signed initData."""
    webapp_url = get_settings().webapp_url
    if not webapp_url:
        return None
    url = f"{webapp_url}#/{route}" if route else webapp_url
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))


def admin_panel_button(route: str = "", text: str = texts.BTN_ADMIN_PANEL) -> InlineKeyboardButton | None:
    """The Admin Panel opened inside Telegram; it signs in with the admin's Telegram account."""
    base = get_settings().base_url
    if not base:
        return None
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=f"{base}/admin/#/{route}"))


def inline(*rows: list[InlineKeyboardButton | None]) -> InlineKeyboardMarkup | None:
    """Build an inline keyboard, skipping buttons that are not available (e.g. no public URL)."""
    clean = [[button for button in row if button is not None] for row in rows]
    clean = [row for row in clean if row]
    return InlineKeyboardMarkup(inline_keyboard=clean) if clean else None


def open_app(webapp_url: str | None, route: str = "") -> InlineKeyboardMarkup | None:
    if not webapp_url:
        return None
    return inline([app_button(route)])


def section_more(route: str) -> InlineKeyboardMarkup | None:
    return inline([app_button(route, texts.BTN_MORE)])


def passport() -> InlineKeyboardMarkup | None:
    return inline(
        [InlineKeyboardButton(text=texts.BTN_PASSPORT_FILE, callback_data="pp:file")],
        [InlineKeyboardButton(text=texts.BTN_CERTIFICATES, callback_data="cert:list")],
        [app_button("profile", texts.BTN_MORE)],
    )


def achievements() -> InlineKeyboardMarkup | None:
    return inline(
        [InlineKeyboardButton(text=texts.BTN_CERTIFICATES, callback_data="cert:list")],
        [app_button("achievements", texts.BTN_MORE)],
    )


def certificates(items: list[tuple[str, str]]) -> InlineKeyboardMarkup | None:
    """One button per certificate: (id, title)."""
    return inline(
        *[
            [InlineKeyboardButton(text=f"📄 {title[:60]}", callback_data=f"cert:get:{cid}")]
            for cid, title in items[:20]
        ],
        [app_button("certificates", texts.BTN_MORE)],
    )


def attendance(scan: bool) -> InlineKeyboardMarkup | None:
    return inline([app_button("checkin?scan=1", texts.BTN_SCAN_QR)] if scan else [app_button("events", texts.BTN_MORE)])


def help_menu() -> InlineKeyboardMarkup | None:
    return inline(
        [InlineKeyboardButton(text=texts.BTN_WRITE_ADMIN, callback_data="sup:new")],
        [app_button("", texts.BTN_OPEN_APP)],
    )


def settings_menu(settings: UserNotificationSettings) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton | None]] = []
    for field, label in texts.NOTIFICATION_LABELS.items():
        enabled = bool(getattr(settings, field))
        rows.append([InlineKeyboardButton(text=f"{'✅' if enabled else '❌'} {label}", callback_data=f"ntf:{field}")])
    rows.append([app_button("profile", texts.BTN_EDIT_PROFILE)])
    markup = inline(*rows)
    assert markup is not None
    return markup


def admin_home() -> InlineKeyboardMarkup | None:
    return inline(
        [admin_panel_button()],
        [admin_panel_button("support", "📨 Murojaatlar"), admin_panel_button("events", "✅ Davomat")],
        [InlineKeyboardButton(text=texts.BTN_ADMIN_LINK, callback_data="adm:link")],
    )


def admin_login(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.BTN_ADMIN_LOGIN, url=url)]])


def write_again() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✍️ Yana yozish", callback_data="sup:new")]])
