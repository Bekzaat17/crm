import uuid

from django.db import models

from crm.accounts.models import User
from crm.sales.models import Lead


class FollowUpTask(models.Model):
    """Задача наследует компанию и ответственного от обращения."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="follow_up_tasks"
    )
    title = models.CharField("Задача", max_length=240)
    due_at = models.DateTimeField("Срок", db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
