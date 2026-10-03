"""All SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""

from app.models.achievement import Achievement, UserAchievement
from app.models.attendance import AttendanceRecord, AttendanceSession, AttendanceToken
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.book import Book, BookQuote, BookRead
from app.models.bot import BotFsmState
from app.models.certificate import Certificate
from app.models.event import Event, EventFeedback, EventRegistration
from app.models.notification import Notification, NotificationTemplate
from app.models.premium import FeatureFlag, Payment, PremiumPlan, PremiumSubscription
from app.models.rbac import LoginToken, Permission, Role, RolePermission, UserPermission, UserRole
from app.models.report import Report, ReportPhoto
from app.models.reward import Reward, RewardCode, UserReward
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
    "BotFsmState",
    "Campaign",
    "CampaignBook",
    "Certificate",
    "Event",
    "EventFeedback",
    "EventRegistration",
    "Faculty",
    "FeatureFlag",
    "LoginToken",
    "Notification",
    "NotificationTemplate",
    "Payment",
    "Permission",
    "PremiumPlan",
    "PremiumSubscription",
    "Report",
    "ReportPhoto",
    "Reward",
    "RewardCode",
    "Role",
    "RolePermission",
    "ScoreTransaction",
    "Season",
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
    "UserNotificationSettings",
    "UserPermission",
    "UserReward",
    "UserRole",
]
