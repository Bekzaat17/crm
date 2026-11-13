"""Напоминания о наступивших сроках, когда CRM закрыта.

Текст нейтральный: без ФИО и названий задач, данные клиента не уходят во
внешние сервисы. Подробности открываются по ссылке после входа в CRM.
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from crm.sales.models import Lead, PipelineStage
from crm.work.models import FollowUpTask

from .models import ReminderDispatch
from .services import enabled_channels, enqueue

# Старые просрочки не рассылаются при первом запуске или после простоя.
WINDOW = timedelta(hours=24)
SUBJECT = "RehubPro CRM"
TEXTS = {
    "task": "Наступил срок задачи по обращению. Откройте CRM, чтобы посмотреть подробности.",
    "contact": "Пора связаться по обращению. Откройте CRM, чтобы посмотреть подробности.",
}


def _remind(kind, object_id, due_at, user, lead, channels):
    try:
        with transaction.atomic():
            ReminderDispatch.objects.create(
                kind=kind, object_id=object_id, due_at=due_at, user=user
            )
            for channel in channels:
                enqueue(
                    channel=channel,
                    kind=f"reminder.{kind}",
                    dedup_key=(
                        f"reminder:{kind}:{object_id}:{due_at.isoformat()}"
                        f":{user.pk}:{channel}"
                    ),
                    subject=SUBJECT,
                    body=TEXTS[kind],
                    url=f"/c/{lead.organization_id}/leads/{lead.id}",
                    user=user,
                )
    except IntegrityError:
        return 0  # уже поставлено другим исполнителем
    return 1


def _not_sent(kind, object_ref, due_ref, user_ref):
    """Ещё нет напоминания этому ответственному на этот срок."""
    return ~Exists(
        ReminderDispatch.objects.filter(
            kind=kind,
            object_id=OuterRef(object_ref),
            due_at=OuterRef(due_ref),
            user_id=OuterRef(user_ref),
        )
    )


def schedule_reminders(now=None):
    now = now or timezone.now()
    since = now - WINDOW
    channels_cache = {}

    def channels(user):
        if user.pk not in channels_cache:
            channels_cache[user.pk] = enabled_channels(user)
        return channels_cache[user.pk]

    created = 0
    tasks = (
        FollowUpTask.objects.filter(
            completed_at__isnull=True,
            due_at__lte=now,
            due_at__gt=since,
            lead__assignee__is_active=True,
        )
        .filter(_not_sent("task", "pk", "due_at", "lead__assignee__user_id"))
        .select_related("lead__assignee__user")
    )
    for task in tasks:
        user = task.lead.assignee.user
        created += _remind(
            "task", task.id, task.due_at, user, task.lead, channels(user)
        )
    leads = (
        Lead.objects.filter(
            next_contact_at__lte=now,
            next_contact_at__gt=since,
            stage__kind=PipelineStage.Kind.OPEN,
            assignee__is_active=True,
        )
        .filter(_not_sent("contact", "pk", "next_contact_at", "assignee__user_id"))
        .select_related("assignee__user")
    )
    for lead in leads:
        user = lead.assignee.user
        created += _remind(
            "contact", lead.id, lead.next_contact_at, user, lead, channels(user)
        )
    return created
