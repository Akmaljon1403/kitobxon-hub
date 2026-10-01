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
from app.models import Faculty, UserNotificationSettings

# Mini App sections (hash routes) opened by the menu buttons.
SECTION_ROUTES = {
    texts.BTN_BOOKS: "books",
    texts.BTN_RANKING: "ranking",
    texts.BTN_EVENTS: "events",
    texts.BTN_TESTS: "tests",
    texts.BTN_RESULTS: "results",
    texts.BTN_ACHIEVEMENTS: "achievements",
    texts.BTN_PROFILE: "profile",
}


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [texts.BTN_BOOKS, texts.BTN_PROFILE],
        [texts.BTN_RANKING, texts.BTN_EVENTS],
        [texts.BTN_TESTS, texts.BTN_RESULTS],
        [texts.BTN_ACHIEVEMENTS, texts.BTN_NOTIFICATIONS],
        [texts.BTN_HELP],
    ]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
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


def open_app(webapp_url: str | None, route: str = "") -> InlineKeyboardMarkup | None:
    """Inline WebApp button. Mini Apps opened from inline buttons receive signed initData."""
    if not webapp_url:
        return None
    url = f"{webapp_url}#/{route}" if route else webapp_url
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=texts.BTN_OPEN_APP, web_app=WebAppInfo(url=url))]]
    )


def notification_settings(settings: UserNotificationSettings) -> InlineKeyboardMarkup:
    rows = []
    for field, label in texts.NOTIFICATION_LABELS.items():
        enabled = bool(getattr(settings, field))
        rows.append([InlineKeyboardButton(text=f"{'✅' if enabled else '❌'} {label}", callback_data=f"ntf:{field}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_login(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.BTN_ADMIN_LOGIN, url=url)]])
