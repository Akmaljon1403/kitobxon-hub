"""Enumerations shared by models, schemas and services."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    INACTIVE = "INACTIVE"
    # Left the club (blocked the bot, or the membership was cancelled). The data is kept for 30 days
    # so a returning member can restore it (14 days: by themselves, 30 days: on request), then erased.
    LEFT = "LEFT"


class SystemRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    USER = "USER"


class SeasonStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class CampaignStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class BookStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class ReadingStatus(StrEnum):
    READING = "READING"
    COMPLETED = "COMPLETED"


class ReadingVerification(StrEnum):
    TEST = "TEST"
    EVENT = "EVENT"
    ADMIN = "ADMIN"


class QuoteStatus(StrEnum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    SENT = "SENT"
    ARCHIVED = "ARCHIVED"


class EventStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RegistrationStatus(StrEnum):
    REGISTERED = "REGISTERED"  # «✅ Qatnashaman»
    DECLINED = "DECLINED"  # «✖️ Bu safar bora olmayman» — a recorded answer, not just an absence
    CANCELLED = "CANCELLED"  # withdrew after registering (legacy; kept for history)


class AttendanceSessionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class AttendanceMethod(StrEnum):
    QR = "QR"
    CODE = "CODE"
    MANUAL = "MANUAL"


class AttendanceStatus(StrEnum):
    VERIFIED = "VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    REVOKED = "REVOKED"
    PENDING = "PENDING"  # added by an administrator, waits for the super administrator's approval


class TestKind(StrEnum):
    __test__ = False  # not a pytest test class

    EVENT = "EVENT"  # «Tadbir testi»: tied to an event, points set by the admin, a scored window
    PERMANENT = "PERMANENT"  # «Doimiy test»: always open, unlimited attempts, points only for the first 100%


class TestStatus(StrEnum):
    __test__ = False  # not a pytest test class

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class QuestionType(StrEnum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"


class TestActivityType(StrEnum):
    __test__ = False

    VISIBILITY_HIDDEN = "VISIBILITY_HIDDEN"
    VISIBILITY_VISIBLE = "VISIBILITY_VISIBLE"
    FOCUS_LOST = "FOCUS_LOST"
    FOCUS_GAINED = "FOCUS_GAINED"
    LEFT_TEST = "LEFT_TEST"
    RETURNED = "RETURNED"
    RECONNECTED = "RECONNECTED"
    TIMEOUT = "TIMEOUT"
    FAST_ANSWER = "FAST_ANSWER"
    OTHER = "OTHER"


class ScoreCategory(StrEnum):
    ATTENDANCE = "ATTENDANCE"
    TEST = "TEST"
    TEST_RANK_BONUS = "TEST_RANK_BONUS"
    BOOK_COMPLETION = "BOOK_COMPLETION"
    CAMPAIGN = "CAMPAIGN"
    ACHIEVEMENT = "ACHIEVEMENT"
    MANUAL = "MANUAL"
    REVERSAL = "REVERSAL"


class AchievementCriteria(StrEnum):
    BOOKS_COMPLETED = "BOOKS_COMPLETED"
    EVENTS_ATTENDED = "EVENTS_ATTENDED"
    TESTS_PASSED = "TESTS_PASSED"
    PERFECT_TESTS = "PERFECT_TESTS"
    ACTIVITY_STREAK_WEEKS = "ACTIVITY_STREAK_WEEKS"
    MONTHLY_TOP_RANK = "MONTHLY_TOP_RANK"
    MANUAL = "MANUAL"
    FRIENDS_INVITED = "FRIENDS_INVITED"  # invited friends who came to a club event


class NotificationType(StrEnum):
    EVENT_CREATED = "EVENT_CREATED"
    EVENT_REMINDER = "EVENT_REMINDER"
    EVENT_STARTED = "EVENT_STARTED"
    ATTENDANCE_OPEN = "ATTENDANCE_OPEN"
    TEST_STARTED = "TEST_STARTED"
    TEST_ENDING = "TEST_ENDING"
    TEST_RESULT = "TEST_RESULT"
    NEW_BOOK = "NEW_BOOK"
    READING_REMINDER = "READING_REMINDER"
    QUOTE_OF_DAY = "QUOTE_OF_DAY"
    RANKING_UPDATE = "RANKING_UPDATE"
    ACHIEVEMENT_UNLOCKED = "ACHIEVEMENT_UNLOCKED"
    REWARD = "REWARD"
    ADMIN_MESSAGE = "ADMIN_MESSAGE"
    SYSTEM = "SYSTEM"
    # Added in revision 0004.
    SUPPORT = "SUPPORT"
    CERTIFICATE = "CERTIFICATE"
    PREMIUM = "PREMIUM"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    FEEDBACK_REQUEST = "FEEDBACK_REQUEST"
    DIGEST = "DIGEST"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class RewardType(StrEnum):
    BOOK = "BOOK"
    CERTIFICATE = "CERTIFICATE"
    SUBSCRIPTION_CODE = "SUBSCRIPTION_CODE"
    PARTNER_DISCOUNT = "PARTNER_DISCOUNT"
    OTHER = "OTHER"


class RewardStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class RewardCodeStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    REDEEMED = "REDEEMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class UserRewardStatus(StrEnum):
    ASSIGNED = "ASSIGNED"
    DELIVERED = "DELIVERED"
    REDEEMED = "REDEEMED"
    REVOKED = "REVOKED"


class ReportStatus(StrEnum):
    DRAFT = "DRAFT"
    AI_GENERATED = "AI_GENERATED"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    PDF_GENERATED = "PDF_GENERATED"
    ARCHIVED = "ARCHIVED"


class SupportTicketStatus(StrEnum):
    OPEN = "OPEN"  # waiting for the club's answer
    ANSWERED = "ANSWERED"
    CLOSED = "CLOSED"


class SupportTicketKind(StrEnum):
    """A general question and a money question are two separate conversations, answered by different
    administrators in different places — they must never share a ticket."""

    GENERAL = "GENERAL"
    PAYMENT = "PAYMENT"


class CertificateKind(StrEnum):
    TEST_PLACE = "TEST_PLACE"  # 1st-3rd place in a test (of an event: only members who attended)
    MONTHLY_TOP = "MONTHLY_TOP"  # 1st-3rd place in last month's ranking
    MANUAL = "MANUAL"  # issued by an administrator
    COMPLETION = "COMPLETION"  # everyone who passed a test (participation / completion certificate)


class ReportKind(StrEnum):
    EVENT = "EVENT"  # one event: attendance, faculties, tests
    PERIOD = "PERIOD"  # a period (e.g. a month): all activity of the club
    GENERAL = "GENERAL"  # any topic: the admin's text and photos


class FeatureMode(StrEnum):
    OFF = "OFF"
    ALL = "ALL"  # every member
    PREMIUM = "PREMIUM"  # premium members only


class PremiumSource(StrEnum):
    STARS = "STARS"  # paid with Telegram Stars
    MANUAL = "MANUAL"  # granted by an administrator (prize, paid in cash, ...)
    CARD = "CARD"  # paid to the club's card, receipt confirmed by the super admin
    TRIAL = "TRIAL"  # the one free trial week of a member
    GIVEAWAY = "GIVEAWAY"  # won in a giveaway (e.g. the first members who joined)
    REFERRAL = "REFERRAL"  # a friend the member invited came to their first event


class PaymentKind(StrEnum):
    PREMIUM = "PREMIUM"
    DONATION = "DONATION"
    STARS = "STARS"  # Telegram Stars bought with a card payment: the admin gifts them in Telegram


class PaymentStatus(StrEnum):
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class CardPaymentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class GiveawayRule(StrEnum):
    RANDOM = "RANDOM"  # random winners among the audience (premium members: 2x chance)
    TEST_TOP = "TEST_TOP"  # most test points in the period
    EVENT_PLACES = "EVENT_PLACES"  # places 1..N of every event's test in the period, each separately
    RANKING_TOP = "RANKING_TOP"  # top N of the club ranking for the period
    NEW_MEMBERS = "NEW_MEMBERS"  # the first N members who joined in the period (awarded as they join)


class GiveawayAudience(StrEnum):
    ALL = "ALL"  # every active member
    ATTENDED = "ATTENDED"  # attended at least one event in the period
    PREMIUM = "PREMIUM"  # premium members only


class GiveawayStatus(StrEnum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"  # drawn automatically at scheduled_at
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class ChannelPostKind(StrEnum):
    EVENT = "EVENT"  # a new event was announced
    EVENT_REMINDER = "EVENT_REMINDER"  # «ertaga soat 15:00 da ... o'qib kelamiz»
    BOOK = "BOOK"  # a new book to read
    READING_NUDGE = "READING_NUDGE"  # «asarni tugatay deb qoldingizmi?»
    QUOTE = "QUOTE"  # quote of the day
    RESULTS = "RESULTS"  # test winners, giveaway winners, the month's leaders
    INVITE = "INVITE"  # weekly invitation to join the bot
    MANUAL = "MANUAL"  # written by an admin
    REPORT = "REPORT"  # «... davra suhbati bo'lib o'tdi» with the photos of an approved event report
    CAMPAIGN = "CAMPAIGN"  # a reading contest («1 hafta — 1 kitob») announcement


class ChannelPostStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GiveawayPrize(StrEnum):
    CODES = "CODES"  # promo codes of a reward
    PREMIUM_DAYS = "PREMIUM_DAYS"  # N days of Premium
    PREMIUM_DISCOUNT = "PREMIUM_DISCOUNT"  # a personal discount (percent) on Premium


class StickerMood(StrEnum):
    """Which messages a saved sticker suits (taken from its emoji)."""

    CELEBRATE = "CELEBRATE"  # wins, places, certificates, Premium
    READING = "READING"  # books, reading reminders, quotes
    WELCOME = "WELCOME"  # greetings, new members, invitations
    ANY = "ANY"


class ContestStatus(StrEnum):
    DRAFT = "DRAFT"  # being prepared, members do not see it
    PUBLISHED = "PUBLISHED"  # announced; runs between starts_at and ends_at
    FINISHED = "FINISHED"  # winners chosen, prizes given
    CANCELLED = "CANCELLED"


class ContestRule(StrEnum):
    """Which invited friends count in a referral contest."""

    REGISTERED = "REGISTERED"  # joined the club through the link (active account)
    ATTENDED = "ATTENDED"  # joined and came to at least one club event before the end
    POINTS = "POINTS"  # joined and earned at least ``min_friend_points`` points before the end


class ShelfStatus(StrEnum):
    """«📚 Javonim»: where a book stands for the member."""

    WANT = "WANT"  # o'qimoqchiman
    READING = "READING"  # o'qiyapman
    FINISHED = "FINISHED"  # o'qib bo'ldim
    LATER = "LATER"  # keyinroq


class MissionMetric(StrEnum):
    """What a personal mission counts (from the member's real activity)."""

    PAGES = "PAGES"  # pages written in the reading diary
    READING_DAYS = "READING_DAYS"  # days with at least one diary entry
    STREAK = "STREAK"  # longest run of consecutive reading days
    BOOKS_FINISHED = "BOOKS_FINISHED"  # books finished on the shelf
    EVENTS = "EVENTS"  # verified club event attendance
    TESTS = "TESTS"  # tests submitted
    QUOTES = "QUOTES"  # quotes saved in the quote box
    REFLECTIONS = "REFLECTIONS"  # «3 savol» answered after a book


class MissionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class UserMissionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


class ContributionKind(StrEnum):
    """«💬 A'zolar fikrlari»: what a member sent to the club."""

    QUOTE = "QUOTE"  # a line from a book
    THOUGHT = "THOUGHT"  # the member's own thought or saying
    BOOK = "BOOK"  # an impression after a book
    EVENT = "EVENT"  # an impression after a club event
    CLUB = "CLUB"  # a testimonial about the club («e'tirof»)


class ContributionStatus(StrEnum):
    PENDING = "PENDING"  # waits for an admin
    APPROVED = "APPROVED"  # in the common feed
    HIDDEN = "HIDDEN"  # not shown (kept for the author)
