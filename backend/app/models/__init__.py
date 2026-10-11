"""All SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""

from app.models.achievement import Achievement, UserAchievement
from app.models.attendance import AttendanceRecord, AttendanceSession, AttendanceToken
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.book import Book, BookQuote, BookRead
from app.models.bot import BotFsmState
from app.models.certificate import Certificate
from app.models.channel import ChannelPost, ChannelSticker, CustomEmoji
from app.models.contest import ReferralContest
from app.models.event import Event, EventFeedback, EventRegistration, EventShift
from app.models.notification import Notification, NotificationTemplate
from app.models.premium import CardPayment, FeatureFlag, Payment, PremiumDiscount, PremiumPlan, PremiumSubscription
from app.models.rbac import LoginToken, Permission, Role, RolePermission, UserPermission, UserRole
from app.models.reading import BookReflection, Mission, ReadingLog, SavedQuote, ShelfItem, UserMission
from app.models.report import Report, ReportPhoto
from app.models.reward import Giveaway, Reward, RewardCode, UserReward
from app.models.score import ScoreTransaction
from app.models.season import Campaign, CampaignBook, Season
from app.models.settings import SystemSetting
from app.models.support import SupportMessage, SupportTicket
from app.models.test import Test, TestActivityLog, TestAnswer, TestAttempt, TestOption, TestQuestion
from app.models.user import Faculty, User, UserNotificationSettings

__all__ = [
    "Achievement",
    "AttendanceRecord",
    "AttendanceSession",
    "AttendanceToken",
    "AuditLog",
    "Base",
    "Book",
    "BookQuote",
    "BookRead",
    "BookReflection",
    "BotFsmState",
    "Campaign",
    "CampaignBook",
    "CardPayment",
    "Certificate",
    "ChannelPost",
    "ChannelSticker",
    "CustomEmoji",
    "Event",
    "EventFeedback",
    "EventRegistration",
    "EventShift",
    "Faculty",
    "FeatureFlag",
    "Giveaway",
    "LoginToken",
    "Mission",
    "Notification",
    "NotificationTemplate",
    "Payment",
    "Permission",
    "PremiumDiscount",
    "PremiumPlan",
    "PremiumSubscription",
    "ReadingLog",
    "ReferralContest",
    "Report",
    "ReportPhoto",
    "Reward",
    "RewardCode",
    "Role",
    "RolePermission",
    "SavedQuote",
    "ScoreTransaction",
    "Season",
    "ShelfItem",
    "SupportMessage",
    "SupportTicket",
    "SystemSetting",
    "Test",
    "TestActivityLog",
    "TestAnswer",
    "TestAttempt",
    "TestOption",
    "TestQuestion",
    "User",
    "UserAchievement",
    "UserMission",
    "UserNotificationSettings",
    "UserPermission",
    "UserReward",
    "UserRole",
]
