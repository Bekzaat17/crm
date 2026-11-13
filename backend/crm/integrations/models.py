import uuid

from django.db import models
from django.utils import timezone

from crm.accounts.models import User
from crm.organizations.models import Organization
from crm.sales.models import Lead


class RehubCenter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    domain = models.CharField(max_length=253)
    encrypted_key = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "domain"], name="crm_unique_center_domain"
            )
        ]


class AdmissionTransfer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "В очереди"
        SENDING = "sending", "Отправляется"
        RETRY = "retry", "Ожидает повтора"
        DELIVERED = "delivered", "Доставлено"
        BLOCKED = "blocked", "Подключение требует внимания"
        FAILED = "failed", "Ошибка передачи"
        CONFLICT = "conflict", "Конфликт данных"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="transfers")
    center = models.ForeignKey(RehubCenter, on_delete=models.PROTECT)
    payload = models.JSONField()
    confirmed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    attempt_count = models.PositiveIntegerField(default=0)
    cycle_attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_until = models.DateTimeField(null=True)
    lease_id = models.UUIDField(null=True)
    resident_id = models.CharField(max_length=100, blank=True)
    last_error = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "center"], name="crm_unique_admission_transfer"
            )
        ]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]


class DeliveryAttempt(models.Model):
    transfer = models.ForeignKey(
        AdmissionTransfer, on_delete=models.CASCADE, related_name="attempts"
    )
    number = models.PositiveIntegerField()
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    outcome = models.CharField(max_length=120, default="unknown")
    http_status = models.PositiveIntegerField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transfer", "number"], name="crm_unique_attempt"
            )
        ]
