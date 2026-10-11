"""Catalogue of permissions.

Codes are stable identifiers stored in the database; descriptions are shown in the Admin Panel.
SUPER_ADMIN implicitly has every permission. ADMIN accounts receive permissions individually
(or through custom roles). Ordinary members (USER) have none of these.
"""

from __future__ import annotations

from enum import StrEnum


class Perm(StrEnum):
    USER_VIEW = "USER_VIEW"
    USER_CONTACT_VIEW = "USER_CONTACT_VIEW"
    USER_MANAGE = "USER_MANAGE"
    BOOK_VIEW = "BOOK_VIEW"
    BOOK_CREATE = "BOOK_CREATE"
    BOOK_EDIT = "BOOK_EDIT"
    BOOK_DELETE = "BOOK_DELETE"
    EVENT_VIEW = "EVENT_VIEW"
    EVENT_CREATE = "EVENT_CREATE"
    EVENT_EDIT = "EVENT_EDIT"
    EVENT_DELETE = "EVENT_DELETE"
    ATTENDANCE_VIEW = "ATTENDANCE_VIEW"
    ATTENDANCE_MANAGE = "ATTENDANCE_MANAGE"
    TEST_VIEW = "TEST_VIEW"
    TEST_CREATE = "TEST_CREATE"
    TEST_EDIT = "TEST_EDIT"
    TEST_DELETE = "TEST_DELETE"
    TEST_PUBLISH = "TEST_PUBLISH"
    SCORE_VIEW = "SCORE_VIEW"
    SCORE_MANAGE = "SCORE_MANAGE"
    REPORT_VIEW = "REPORT_VIEW"
    REPORT_CREATE = "REPORT_CREATE"
    REPORT_APPROVE = "REPORT_APPROVE"
    NOTIFICATION_SEND = "NOTIFICATION_SEND"
    ANALYTICS_VIEW = "ANALYTICS_VIEW"
    REWARD_MANAGE = "REWARD_MANAGE"
    SEASON_MANAGE = "SEASON_MANAGE"
    SETTINGS_MANAGE = "SETTINGS_MANAGE"
    AUDIT_LOG_VIEW = "AUDIT_LOG_VIEW"
    SUPPORT_MANAGE = "SUPPORT_MANAGE"
    STARS_SEND = "STARS_SEND"


# (group, description shown to administrators)
PERMISSION_INFO: dict[Perm, tuple[str, str]] = {
    Perm.USER_VIEW: ("users", "A'zolar ro'yxatini va profillarini ko'rish"),
    Perm.USER_CONTACT_VIEW: ("users", "A'zolarning telefon raqamlarini ko'rish"),
    Perm.USER_MANAGE: ("users", "A'zolarni tasdiqlash, bloklash va ma'lumotlarini tahrirlash"),
    Perm.BOOK_VIEW: ("books", "Kitoblarni (qoralamalar bilan) ko'rish"),
    Perm.BOOK_CREATE: ("books", "Kitob va iqtibos qo'shish"),
    Perm.BOOK_EDIT: ("books", "Kitob va iqtiboslarni tahrirlash, arxivlash"),
    Perm.BOOK_DELETE: ("books", "Kitob va iqtiboslarni o'chirish"),
    Perm.EVENT_VIEW: ("events", "Tadbirlarni (qoralamalar bilan) ko'rish"),
    Perm.EVENT_CREATE: ("events", "Tadbir yaratish"),
    Perm.EVENT_EDIT: ("events", "Tadbirni tahrirlash va bekor qilish"),
    Perm.EVENT_DELETE: ("events", "Tadbirni o'chirish"),
    Perm.ATTENDANCE_VIEW: ("attendance", "Davomatni ko'rish va eksport qilish"),
    Perm.ATTENDANCE_MANAGE: ("attendance", "Davomatni ochish/yopish, qo'lda tasdiqlash va tuzatish"),
    Perm.TEST_VIEW: ("tests", "Testlar va natijalarni ko'rish"),
    Perm.TEST_CREATE: ("tests", "Test yaratish"),
    Perm.TEST_EDIT: ("tests", "Testni tahrirlash"),
    Perm.TEST_DELETE: ("tests", "Testni o'chirish"),
    Perm.TEST_PUBLISH: ("tests", "Testni e'lon qilish va yopish"),
    Perm.SCORE_VIEW: ("scores", "Ballar tarixini ko'rish"),
    Perm.SCORE_MANAGE: ("scores", "Ballarni qo'lda o'zgartirish (sabab ko'rsatilishi shart)"),
    Perm.REPORT_VIEW: ("reports", "Hisobotlarni ko'rish va yuklab olish"),
    Perm.REPORT_CREATE: ("reports", "Hisobot tayyorlash va tahrirlash"),
    Perm.REPORT_APPROVE: ("reports", "Hisobotni tasdiqlash va PDF yaratish"),
    Perm.NOTIFICATION_SEND: ("notifications", "A'zolarga xabar yuborish"),
    Perm.ANALYTICS_VIEW: ("analytics", "Statistika va tahlillarni ko'rish"),
    Perm.REWARD_MANAGE: ("rewards", "Sovg'alar, promo-kodlar va sertifikatlarni boshqarish"),
    Perm.SEASON_MANAGE: ("seasons", "Mavsumlar va kitobxonlik kampaniyalarini boshqarish"),
    Perm.SETTINGS_MANAGE: ("system", "Tizim sozlamalari, ball qoidalari va fakultetlarni o'zgartirish"),
    Perm.AUDIT_LOG_VIEW: ("system", "Audit jurnalini ko'rish"),
    Perm.SUPPORT_MANAGE: ("support", "A'zolar murojaatlarini o'qish va ularga javob berish"),
    Perm.STARS_SEND: (
        "payments",
        "Telegram Stars'ni a'zolarga yuborish: bosh admin tasdiqlagan Stars buyurtmalari shu adminga keladi",
    ),
}

assert set(PERMISSION_INFO) == set(Perm), "Every permission needs a description"
