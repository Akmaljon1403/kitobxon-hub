"""All SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""

from app.models.achievement import Achievement, UserAchievement
from app.models.attendance import AttendanceRecord, AttendanceSession, AttendanceToken
from app.models.audit import AuditLog
from app.models.backup import Backup
from app.models.base import Base
from app.models.book import Book, BookQuote, BookRead
from app.models.bot import BotFsmState, TextOverride
from app.models.certificate import Certificate, CertificateTemplate
from app.models.channel import ChannelPost, ChannelSticker, CustomEmoji
from app.models.community import Contribution, ContributionLike, PaymentsChatLink
from app.models.contest import ReferralContest
from app.models.event import Event, EventFeedback, EventRegistration, EventShift
from app.models.notification import Notification, NotificationTemplate
from app.models.premium import CardPayment, FeatureFlag, Payment, PremiumDiscount, PremiumPlan, PremiumSubscription
from app.models.rbac import LoginToken, Permission, Role, RolePermission, UserPermission, UserRole
from app.models.reading import BookReflection, Mission, ReadingLog, SavedQuote, ShelfItem, UserMission
from app.models.rental import LicenceIssuer, RentalLicence, RentalOrganization, RentalPayment
from app.models.report import Report, ReportPhoto
from app.models.reward import Giveaway, Reward, RewardCode, UserReward
from app.models.score import ScoreTransaction
from app.models.season import Campaign, CampaignBook, CampaignParticipant, Season
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
    "Backup",
    "Base",
    "Book",
    "BookQuote",
    "BookRead",
    "BookReflection",
    "BotFsmState",
    "Campaign",
    "CampaignBook",
    "CampaignParticipant",
    "CardPayment",
    "Certificate",
    "CertificateTemplate",
    "ChannelPost",
    "ChannelSticker",
    "Contribution",
    "ContributionLike",
    "CustomEmoji",
    "Event",
    "EventFeedback",
    "EventRegistration",
    "EventShift",
    "Faculty",
    "FeatureFlag",
    "Giveaway",
    "LicenceIssuer",
    "LoginToken",
    "Mission",
    "Notification",
    "NotificationTemplate",
    "Payment",
    "PaymentsChatLink",
    "Permission",
    "PremiumDiscount",
    "PremiumPlan",
    "PremiumSubscription",
    "ReadingLog",
    "ReferralContest",
    "RentalLicence",
    "RentalOrganization",
    "RentalPayment",
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
    "TextOverride",
    "User",
    "UserAchievement",
    "UserMission",
    "UserNotificationSettings",
    "UserPermission",
    "UserReward",
    "UserRole",
]
