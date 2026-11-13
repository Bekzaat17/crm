from django.utils import timezone


def task_data(task):
    return {
        "id": str(task.id),
        "title": task.title,
        "lead_id": str(task.lead_id),
        "lead_title": task.lead.title,
        "client_name": task.lead.client.name,
        "assignee_name": task.lead.assignee.user.name,
        "due_at": task.due_at.isoformat(),
        "completed": bool(task.completed_at),
        "overdue": not task.completed_at and task.due_at <= timezone.now(),
        "version": task.version,
    }
