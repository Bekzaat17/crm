from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from crm.core.errors import ApiError
from crm.sales.models import PipelineStage
from crm.sales.selectors import clients_for, leads_for

from .models import FollowUpTask


def tasks_for(member):
    return FollowUpTask.objects.filter(lead__in=leads_for(member))


def find_task(member, task_id, lock=False):
    queryset = tasks_for(member)
    if lock:
        queryset = queryset.select_for_update()
    task = queryset.filter(pk=task_id).first()
    if task is None:
        raise ApiError("Задача не найдена.", 404)
    return task


def filtered_tasks(member, status):
    queryset = tasks_for(member)
    now = timezone.now()
    tomorrow = timezone.make_aware(
        datetime.combine(timezone.localdate() + timedelta(days=1), time.min)
    )
    filters = {
        "open": Q(completed_at__isnull=True),
        "overdue": Q(completed_at__isnull=True, due_at__lte=now),
        "today": Q(completed_at__isnull=True, due_at__gt=now, due_at__lt=tomorrow),
        "completed": Q(completed_at__isnull=False),
        "all": Q(),
    }
    if status not in filters:
        raise ApiError("Неизвестный фильтр задач.")
    return queryset.filter(filters[status]).order_by("due_at", "id")


def open_leads(leads):
    return leads.filter(stage__kind=PipelineStage.Kind.OPEN)


def sales_summary(member):
    leads = leads_for(member)
    tasks = tasks_for(member)
    by_stage = {
        str(row["stage"]): row["count"]
        for row in leads.values("stage").annotate(count=Count("id"))
    }
    by_kind = {
        row["stage__kind"]: row["count"]
        for row in leads.values("stage__kind").annotate(count=Count("id"))
    }
    now = timezone.now()
    return {
        "clients": clients_for(member).count(),
        "leads": sum(by_stage.values()),
        "stages": by_stage,
        "active_leads": by_kind.get(PipelineStage.Kind.OPEN, 0),
        "admitted": by_kind.get(PipelineStage.Kind.ADMITTED, 0),
        "refused": by_kind.get(PipelineStage.Kind.REFUSED, 0),
        "open_tasks": tasks.filter(completed_at__isnull=True).count(),
        "overdue_tasks": tasks.filter(
            completed_at__isnull=True, due_at__lte=now
        ).count(),
        "contacts_due": open_leads(leads).filter(next_contact_at__lte=now).count(),
    }
