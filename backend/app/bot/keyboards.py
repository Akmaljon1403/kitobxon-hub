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
    (texts.BTN_BENEFIT, texts.BTN_SETTINGS),
    (texts.BTN_HELP,),
)
MENU_BUTTONS = frozenset(label for row in MEMBER_ROWS for label in row) | {texts.BTN_ADMIN, texts.BTN_PREMIUM}


def main_menu(
    *, is_admin: bool = False, hidden: frozenset[str] = frozenset(), premium: bool = False
) -> ReplyKeyboardMarkup:
    """``hidden``: sections switched off by the super admin (the others close up two per row);
    ``premium``: the Premium store is open, so its button is shown."""
    labels = [label for row in MEMBER_ROWS for label in row if label not in hidden]
    labels += [label for label, shown in ((texts.BTN_PREMIUM, premium), (texts.BTN_ADMIN, is_admin)) if shown]
    rows = [labels[index : index + 2] for index in range(0, len(labels), 2)]
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


def subscribe(channels: list[tuple[str, str]], check_data: str) -> InlineKeyboardMarkup | None:
    """channels: (title, link); the last button checks the subscription again."""
    return inline(
        *[[InlineKeyboardButton(text=f"📢 {title[:40]}", url=url)] for title, url in channels],
        [InlineKeyboardButton(text=texts.BTN_SUBSCRIBED, callback_data=check_data)],
    )


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
        [InlineKeyboardButton(text=texts.BTN_FAQ, callback_data="faq:list")],
        [InlineKeyboardButton(text=texts.BTN_WRITE_ADMIN, callback_data="sup:new")] if support else [],
        [InlineKeyboardButton(text=texts.BTN_PREMIUM, callback_data="prem:open")] if premium else [],
        [InlineKeyboardButton(text=texts.BTN_DONATE, callback_data="don:open")] if donations else [],
        [app_button("", texts.BTN_OPEN_APP)],
    )


def faq_topics(topics: list[tuple[str, str]]) -> InlineKeyboardMarkup | None:
    """topics: (code, title), two per row."""
    buttons = [InlineKeyboardButton(text=title, callback_data=f"faq:t:{code}") for code, title in topics]
    return inline(
        *[buttons[index : index + 2] for index in range(0, len(buttons), 2)],
        [app_button("help", texts.BTN_FAQ_APP)],
    )


def faq_answer(*, support: bool) -> InlineKeyboardMarkup | None:
    return inline(
        [InlineKeyboardButton(text=texts.BTN_FAQ_BACK, callback_data="faq:list")],
        [InlineKeyboardButton(text=texts.BTN_WRITE_ADMIN, callback_data="sup:new")] if support else [],
    )


def limited_account() -> InlineKeyboardMarkup | None:
    """A blocked or not yet approved member may still read the answers and write to the admins."""
    return inline(
        [InlineKeyboardButton(text=texts.BTN_WRITE_ADMIN, callback_data="sup:new")],
        [InlineKeyboardButton(text=texts.BTN_FAQ, callback_data="faq:list")],
    )


def left_member(bot_username: str | None) -> InlineKeyboardMarkup | None:
    """A member who left: come back (sends /start by itself) or clear the chat."""
    restore = (
        InlineKeyboardButton(text=texts.BTN_LEFT_RESTORE, url=f"https://t.me/{bot_username}?start=qayta")
        if bot_username
        else InlineKeyboardButton(text=texts.BTN_LEFT_RESTORE, callback_data="mem:back")
    )
    return inline([restore], [InlineKeyboardButton(text=texts.BTN_LEFT_WIPE, callback_data="mem:wipe")])


def premium_offer() -> InlineKeyboardMarkup | None:
    return inline([InlineKeyboardButton(text=texts.BTN_PREMIUM, callback_data="prem:open")])


def premium_methods(*, card: bool, stars: bool, donations: bool) -> InlineKeyboardMarkup | None:
    """The Premium section: first how to pay (the bank card first — most students have one), then the plans."""
    return inline(
        [InlineKeyboardButton(text=texts.BTN_PAY_CARD, callback_data="card:open")] if card else [],
        [InlineKeyboardButton(text=texts.BTN_PAY_STARS, callback_data="prem:stars")] if stars else [],
        [InlineKeyboardButton(text=texts.BTN_DONATE, callback_data="don:open")] if donations else [],
        [app_button("premium", texts.BTN_MORE)],
    )


def premium_plans(plans: list[tuple[str, str]]) -> InlineKeyboardMarkup | None:
    """Plans paid with Telegram Stars: (plan id hex, button text)."""
    return inline(
        *[[InlineKeyboardButton(text=label, callback_data=f"prem:buy:{plan_id}")] for plan_id, label in plans],
        [InlineKeyboardButton(text=texts.BTN_BACK_TO_METHODS, callback_data="prem:open")],
    )


def card_plans(plans: list[tuple[str, str]], *, stars: bool = False) -> InlineKeyboardMarkup | None:
    """plans: (plan id hex, button text). Stars bought with the card hide behind one «⭐ Stars sotib olish»
    button, so the Premium plans are not lost among the packages."""
    return inline(
        *[[InlineKeyboardButton(text=label, callback_data=f"card:plan:{plan_id}")] for plan_id, label in plans],
        [InlineKeyboardButton(text=texts.BTN_BUY_STARS, callback_data="card:starsmenu")] if stars else [],
        [InlineKeyboardButton(text=texts.BTN_BACK_TO_METHODS, callback_data="prem:open")],
    )


def card_stars_menu(stars: list[tuple[int, str]]) -> InlineKeyboardMarkup | None:
    """stars: (amount, button text) — the packages, two in a row, and back to the card menu."""
    buttons = [InlineKeyboardButton(text=label, callback_data=f"card:stars:{amount}") for amount, label in stars]
    return inline(
        *[buttons[index : index + 2] for index in range(0, len(buttons), 2)],
        [InlineKeyboardButton(text=texts.BTN_BACK, callback_data="card:back")],
    )


def donation_methods(*, card: bool, amounts: list[int]) -> InlineKeyboardMarkup | None:
    """«Klubni qo'llab-quvvatlash»: to the club's card (no receipt needed) or with Telegram Stars."""
    star_buttons = [InlineKeyboardButton(text=f"{amount} ⭐", callback_data=f"don:{amount}") for amount in amounts]
    return inline(
        [InlineKeyboardButton(text=texts.BTN_DONATE_CARD, callback_data="don:card")] if card else [],
        star_buttons,
    )


def donation_done() -> InlineKeyboardMarkup | None:
    return inline([InlineKeyboardButton(text=texts.BTN_DONATE_DONE, callback_data="don:done")])


def stars_sent(payment_hex: str) -> InlineKeyboardMarkup | None:
    return inline([InlineKeyboardButton(text=texts.BTN_STARS_SENT, callback_data=f"cp:sent:{payment_hex}")])


def card_decision(payment_hex: str, *, view: bool = False) -> InlineKeyboardMarkup | None:
    return inline(
        [InlineKeyboardButton(text=texts.BTN_VIEW_RECEIPT, callback_data=f"cp:view:{payment_hex}")] if view else [],
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"cp:ok:{payment_hex}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"cp:no:{payment_hex}"),
        ],
    )


def card_reject_reasons(payment_hex: str) -> InlineKeyboardMarkup | None:
    return inline(
        *[
            [InlineKeyboardButton(text=f"• {reason}", callback_data=f"cp:nr:{payment_hex}:{index}")]
            for index, reason in enumerate(texts.CARD_REJECT_REASONS)
        ],
        [InlineKeyboardButton(text=texts.BTN_REJECT_OTHER, callback_data=f"cp:nw:{payment_hex}")],
        [InlineKeyboardButton(text=texts.BTN_BACK, callback_data=f"cp:back:{payment_hex}")],
    )


def card_decided(payment_hex: str, *, stars_to_send: bool) -> InlineKeyboardMarkup | None:
    """After a decision: «Stars yuborildi» (when Stars are still to be gifted) and «↩️ Qaytarish»."""
    return inline(
        [InlineKeyboardButton(text=texts.BTN_STARS_SENT, callback_data=f"cp:sent:{payment_hex}")]
        if stars_to_send
        else [],
        [InlineKeyboardButton(text=texts.BTN_UNDO, callback_data=f"cp:undo:{payment_hex}")],
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


def emoji_tools(has_any: bool) -> InlineKeyboardMarkup | None:
    """/emoji: check that Telegram shows the premium emoji, see and remove them one by one, or all."""
    return inline(
        [InlineKeyboardButton(text=texts.BTN_EMOJI_TEST, callback_data="emj:test")] if has_any else [],
        [InlineKeyboardButton(text=texts.BTN_EMOJI_LIST, callback_data="emj:list")] if has_any else [],
        [InlineKeyboardButton(text=texts.BTN_EMOJI_CLEAR, callback_data="emj:clear")] if has_any else [],
    )


def sticker_overview(total: int) -> InlineKeyboardMarkup | None:
    """/stiker: see the saved stickers (each with a delete button)."""
    return inline([InlineKeyboardButton(text=texts.BTN_STICKER_LIST, callback_data="stk:list")] if total else [])


def sticker_delete(sticker_id: object) -> InlineKeyboardMarkup:
    return inline([InlineKeyboardButton(text=texts.BTN_STICKER_DELETE, callback_data=f"stk:del:{sticker_id}")])


def emoji_delete_list(rows: list[tuple[str, str]]) -> InlineKeyboardMarkup | None:
    """One button per saved emoji; pressing it removes that emoji (value: the plain emoji)."""
    return inline(
        *[[InlineKeyboardButton(text=f"🗑 {emoji}", callback_data=f"emj:del:{emoji}")] for emoji, _ in rows[:60]]
    )


def decor_offer() -> InlineKeyboardMarkup | None:
    return inline(
        [
            InlineKeyboardButton(text=texts.BTN_DECOR_SAVE, callback_data="dec:save"),
            InlineKeyboardButton(text=texts.BTN_DECOR_SKIP, callback_data="dec:skip"),
        ]
    )


def reading_links(*, missions: bool = False) -> InlineKeyboardMarkup | None:
    """«📚 Javonim» (and «🎯 Missiyalar») in the Mini App."""
    return inline(
        [app_button("shelf", texts.BTN_SHELF_APP)],
        [app_button("missions", texts.BTN_MISSIONS_APP)] if missions else [],
    )


def community_start() -> InlineKeyboardMarkup | None:
    from app.models.enums import ContributionKind
    from app.services.community import KINDS

    choices = (ContributionKind.QUOTE, ContributionKind.THOUGHT, ContributionKind.CLUB)
    return inline(
        *[[InlineKeyboardButton(text=KINDS[kind][0], callback_data=f"cmw:{kind.value}")] for kind in choices],
        [app_button("community/new", texts.BTN_COMMUNITY_APP)],
        [app_button("community", texts.BTN_COMMUNITY_FEED)],
    )


def community_skip() -> InlineKeyboardMarkup | None:
    return inline([InlineKeyboardButton(text=texts.BTN_SKIP, callback_data="cmw:skip")])


def community_sent(contribution_hex: str) -> InlineKeyboardMarkup | None:
    return inline(
        [InlineKeyboardButton(text=texts.BTN_COMMUNITY_CARD, callback_data=f"cm:card:{contribution_hex}")],
        [app_button("community", texts.BTN_COMMUNITY_FEED)],
    )


def community_event_offer(event_hex: str) -> InlineKeyboardMarkup | None:
    return inline(
        [
            InlineKeyboardButton(text=texts.BTN_COMMUNITY_EVENT_YES, callback_data=f"cmfb:{event_hex}"),
            InlineKeyboardButton(text=texts.BTN_COMMUNITY_EVENT_NO, callback_data="cmfb:no"),
        ]
    )


def community_admin_after() -> InlineKeyboardMarkup | None:
    """Under a decided text: the full section (card designs, the channel, members, the quote of the day)."""
    return inline([admin_panel_button("community", "🛠 Kanalga yoki a'zolarga ulashish — panelda")])
