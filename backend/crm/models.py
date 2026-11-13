"""Реестр моделей приложения crm. Модели принадлежат доменным пакетам."""

from crm.accounts.models import User, UserManager
from crm.conversations.models import (
    Conversation,
    ExtensionToken,
    ImportBatch,
    Message,
)
from crm.core.models import RateLimitBucket
from crm.integrations.models import AdmissionTransfer, DeliveryAttempt, RehubCenter
from crm.notifications.models import (
    NotificationPreference,
    OutboundMessage,
    PushSubscription,
    ReminderDispatch,
    TelegramCursor,
    TelegramLink,
    TelegramLinkToken,
)
from crm.organizations.models import (
    AuditEvent,
    Branch,
    Invitation,
    Membership,
    Organization,
)
from crm.sales.models import (
    Client,
    Lead,
    LeadActivity,
    PipelineStage,
    RelatedContact,
)
from crm.work.models import FollowUpTask

__all__ = [
    "Conversation",
    "ExtensionToken",
    "ImportBatch",
    "Message",
    "NotificationPreference",
    "OutboundMessage",
    "PushSubscription",
    "ReminderDispatch",
    "TelegramCursor",
    "TelegramLink",
    "TelegramLinkToken",
    "AdmissionTransfer",
    "AuditEvent",
    "Branch",
    "Client",
    "DeliveryAttempt",
    "FollowUpTask",
    "Invitation",
    "Lead",
    "LeadActivity",
    "Membership",
    "Organization",
    "PipelineStage",
    "RateLimitBucket",
    "RehubCenter",
    "RelatedContact",
    "User",
    "UserManager",
]
