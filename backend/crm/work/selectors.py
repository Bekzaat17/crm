from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from crm.models import FollowUpTask, Lead
from crm.sales.selectors import clients_for, leads_for
from crm.services import ApiError


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
        "overdue": Q(completed_at__isnull=True, due_at__lt=now),
        "today": Q(completed_at__isnull=True, due_at__gte=now, due_at__lt=tomorrow),
        "completed": Q(completed_at__isnull=False),
        "all": Q(),
    }
    if status not in filters:
        raise ApiError("Неизвестный фильтр задач.")
    return queryset.filter(filters[status]).order_by("due_at", "id")


def sales_summary(member):
    leads = leads_for(member)
    tasks = tasks_for(member)
    counts = {
        row["stage"]: row["count"]
        for row in leads.values("stage").annotate(count=Count("id"))
    }
    overdue = tasks.filter(
        completed_at__isnull=True, due_at__lte=timezone.now()
    ).count()
    contacts_due = (
        leads.filter(next_contact_at__lte=timezone.now())
        .exclude(stage__in=[Lead.Stage.ADMITTED, Lead.Stage.REFUSED])
        .count()
    )
    return {
        "clients": clients_for(member).count(),
        "leads": sum(counts.values()),
        "stages": counts,
        "active_leads": sum(
            value
            for stage, value in counts.items()
            if stage not in (Lead.Stage.ADMITTED, Lead.Stage.REFUSED)
        ),
        "admitted": counts.get(Lead.Stage.ADMITTED, 0),
        "refused": counts.get(Lead.Stage.REFUSED, 0),
        "open_tasks": tasks.filter(completed_at__isnull=True).count(),
        "overdue_tasks": overdue,
        "contacts_due": contacts_due,
    }
