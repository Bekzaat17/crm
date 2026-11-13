from django.db import transaction
from django.utils import timezone

from crm.core.errors import ApiError
from crm.core.validation import aware_datetime, clean_text, require_version
from crm.organizations.context import get_membership
from crm.sales.models import LeadActivity
from crm.sales.selectors import find_lead

from .models import FollowUpTask
from .selectors import find_task


def parse_due_at(value):
    return aware_datetime(
        value, "Укажите срок задачи с датой, временем и часовым поясом."
    )


@transaction.atomic
def create_task(actor, company_id, lead_id, data):
    member = get_membership(actor, company_id)
    lead = find_lead(member, lead_id, lock=True)
    task = FollowUpTask.objects.create(
        lead=lead,
        created_by=actor,
        title=clean_text(data.get("title"), "Название задачи", 240),
        due_at=parse_due_at(data.get("due_at")),
    )
    LeadActivity.objects.create(
        lead=lead, actor=actor, kind="task", text=f"Добавлена задача: {task.title}"
    )
    return task


@transaction.atomic
def update_task(actor, company_id, task_id, data):
    member = get_membership(actor, company_id)
    task = find_task(member, task_id, lock=True)
    require_version(task, data, "Задача изменилась. Обновите список.")
    changes = []
    if "title" in data:
        title = clean_text(data["title"], "Название задачи", 240)
        if title != task.title:
            task.title = title
            changes.append("Изменено название задачи")
    if "due_at" in data:
        due_at = parse_due_at(data["due_at"])
        if due_at != task.due_at:
            task.due_at = due_at
            changes.append("Перенесён срок задачи")
    if "completed" in data:
        if not isinstance(data["completed"], bool):
            raise ApiError("Состояние выполнения должно быть логическим значением.")
        if data["completed"] != bool(task.completed_at):
            task.completed_at = timezone.now() if data["completed"] else None
            changes.append(
                "Задача выполнена"
                if task.completed_at
                else "Задача возвращена в работу"
            )
    task.version += 1
    task.save()
    if changes:
        LeadActivity.objects.create(
            lead=task.lead,
            actor=actor,
            kind="task",
            text=f"{'; '.join(changes)}: {task.title}",
        )
    return task
