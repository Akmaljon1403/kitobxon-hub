"""Enumerations shared by models, schemas and services."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    INACTIVE = "INACTIVE"


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
    REGISTERED = "REGISTERED"
    CANCELLED = "CANCELLED"


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


class CertificateKind(StrEnum):
    TEST_PLACE = "TEST_PLACE"  # 1st-3rd place in a test (of an event: only members who attended)
    MONTHLY_TOP = "MONTHLY_TOP"  # 1st-3rd place in last month's ranking
    MANUAL = "MANUAL"  # issued by an administrator


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


class PaymentKind(StrEnum):
    PREMIUM = "PREMIUM"
    DONATION = "DONATION"


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


class ChannelPostStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
