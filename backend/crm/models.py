"""Реестр моделей приложения crm. Модели принадлежат доменным пакетам."""

from crm.accounts.models import Registration, User, UserManager
from crm.core.models import RateLimitBucket
from crm.integrations.models import AdmissionTransfer, DeliveryAttempt, RehubCenter
from crm.organizations.models import (
    AuditEvent,
    Branch,
    Invitation,
    Membership,
    Organization,
)
from crm.sales.models import Client, Lead, LeadActivity, RelatedContact
from crm.work.models import FollowUpTask

__all__ = [
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
    "RateLimitBucket",
    "RehubCenter",
    "Registration",
    "RelatedContact",
    "User",
    "UserManager",
]
