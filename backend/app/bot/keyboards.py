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
MENU_BUTTONS = frozenset(label for row in MEMBER_ROWS for label in row) | {texts.BTN_ADMIN, texts.BTN_PREMIUM}


def main_menu(
    *, is_admin: bool = False, hidden: frozenset[str] = frozenset(), premium: bool = False
) -> ReplyKeyboardMarkup:
    """``hidden``: sections switched off by the super admin (the others close up two per row);
    ``premium``: the Premium store is open, so its button is shown."""
    labels = [label for row in MEMBER_ROWS for label in row if label not in hidden]
    rows = [labels[index : index + 2] for index in range(0, len(labels), 2)]
    extra = [label for label, shown in ((texts.BTN_PREMIUM, premium), (texts.BTN_ADMIN, is_admin)) if shown]
    if extra:
        rows.append(extra)
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


def passport(*, own_photo: bool = False) -> InlineKeyboardMarkup | None:
    return inline(
        [InlineKeyboardButton(text=texts.BTN_PASSPORT_PHOTO, callback_data="pp:photo")],
        [InlineKeyboardButton(text=texts.BTN_PASSPORT_RESET, callback_data="pp:reset")] if own_photo else [],
        [
            InlineKeyboardButton(text=texts.BTN_PASSPORT_THEME, callback_data="pp:themes"),
            InlineKeyboardButton(text=texts.BTN_PASSPORT_FILE, callback_data="pp:file"),
        ],
        [app_button("certificates", texts.BTN_CERTIFICATES)],
        [app_button("profile", texts.BTN_MORE)],
    )


def passport_themes(themes: list[tuple[str, str, bool]]) -> InlineKeyboardMarkup | None:
    """themes: (code, title, selected)."""
    buttons = [
        InlineKeyboardButton(text=f"{'✅ ' if selected else ''}{title}", callback_data=f"pp:theme:{code}")
        for code, title, selected in themes
    ]
    return inline(*[buttons[index : index + 2] for index in range(0, len(buttons), 2)])


def achievements() -> InlineKeyboardMarkup | None:
    return inline(
        [app_button("certificates", texts.BTN_CERTIFICATES)],
        [InlineKeyboardButton(text=texts.BTN_PORTFOLIO, callback_data="pf:get")],
        [InlineKeyboardButton(text=texts.BTN_INVITE, callback_data="ref:open")],
        [app_button("achievements", texts.BTN_MORE)],
    )


def attendance(scan: bool) -> InlineKeyboardMarkup | None:
    return inline([app_button("checkin?scan=1", texts.BTN_SCAN_QR)] if scan else [app_button("events", texts.BTN_MORE)])


def help_menu(*, support: bool = True, premium: bool = False, donations: bool = False) -> InlineKeyboardMarkup | None:
    return inline(
        [InlineKeyboardButton(text=texts.BTN_WRITE_ADMIN, callback_data="sup:new")] if support else [],
        [InlineKeyboardButton(text=texts.BTN_PREMIUM, callback_data="prem:open")] if premium else [],
        [InlineKeyboardButton(text=texts.BTN_DONATE, callback_data="don:open")] if donations else [],
        [app_button("", texts.BTN_OPEN_APP)],
    )


def premium_offer() -> InlineKeyboardMarkup | None:
    return inline([InlineKeyboardButton(text=texts.BTN_PREMIUM, callback_data="prem:open")])


def premium_plans(
    plans: list[tuple[str, str]], *, donations: bool, card: bool = False, trial_days: int = 0
) -> InlineKeyboardMarkup | None:
    """plans: (plan id hex, button text)."""
    return inline(
        [InlineKeyboardButton(text=texts.BTN_TRIAL.format(days=trial_days), callback_data="prem:trial")]
        if trial_days
        else [],
        *[[InlineKeyboardButton(text=label, callback_data=f"prem:buy:{plan_id}")] for plan_id, label in plans],
        [InlineKeyboardButton(text=texts.BTN_PAY_CARD, callback_data="card:open")] if card else [],
        [InlineKeyboardButton(text=texts.BTN_DONATE, callback_data="don:open")] if donations else [],
        [app_button("premium", texts.BTN_MORE)],
    )


def card_plans(plans: list[tuple[str, str]], stars: list[tuple[int, str]] | None = None) -> InlineKeyboardMarkup | None:
    """plans: (plan id hex, button text); stars: (amount, button text); the last button is a donation."""
    star_buttons = [
        InlineKeyboardButton(text=label, callback_data=f"card:stars:{amount}") for amount, label in stars or []
    ]
    return inline(
        *[[InlineKeyboardButton(text=label, callback_data=f"card:plan:{plan_id}")] for plan_id, label in plans],
        *[star_buttons[index : index + 2] for index in range(0, len(star_buttons), 2)],
        [InlineKeyboardButton(text=texts.CARD_DONATE, callback_data="card:don")],
    )


def stars_sent(payment_hex: str) -> InlineKeyboardMarkup | None:
    return inline([InlineKeyboardButton(text=texts.BTN_STARS_SENT, callback_data=f"cp:sent:{payment_hex}")])


def card_decision(payment_hex: str) -> InlineKeyboardMarkup | None:
    return inline(
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"cp:ok:{payment_hex}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"cp:no:{payment_hex}"),
        ]
    )


def donation_amounts(amounts: list[int]) -> InlineKeyboardMarkup | None:
    return inline([InlineKeyboardButton(text=f"{amount} ⭐", callback_data=f"don:{amount}") for amount in amounts])


def feedback_comment(event_hex: str) -> InlineKeyboardMarkup | None:
    return inline([InlineKeyboardButton(text=texts.BTN_FEEDBACK_COMMENT, callback_data=f"fbc:{event_hex}")])


def settings_menu(settings: UserNotificationSettings) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton | None]] = []
    for field, label in texts.NOTIFICATION_LABELS.items():
        enabled = bool(getattr(settings, field))
        rows.append([InlineKeyboardButton(text=f"{'✅' if enabled else '❌'} {label}", callback_data=f"ntf:{field}")])
    rows.append([app_button("profile", texts.BTN_EDIT_PROFILE)])
    rows.append([InlineKeyboardButton(text=texts.BTN_LEAVE, callback_data="mem:leave")])
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
