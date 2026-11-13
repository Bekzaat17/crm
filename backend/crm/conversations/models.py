import uuid

from django.db import models

from crm.accounts.models import User
from crm.organizations.models import Organization
from crm.sales.models import Lead


class Source(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp"
    INSTAGRAM = "instagram", "Instagram"
    TELEGRAM = "telegram", "Telegram"


class ExtensionToken(models.Model):
    """Отзываемый доступ расширения браузера: один сотрудник, одна компания."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    name = models.CharField(max_length=80)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)
    last_used_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Conversation(models.Model):
    """Внешний диалог. Собеседник не объединяется с клиентом автоматически:
    диалог привязывается к обращению явным выбором сотрудника."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    source = models.CharField(max_length=20, choices=Source.choices)
    external_id = models.CharField(max_length=200)
    title = models.CharField(max_length=200)
    lead = models.ForeignKey(
        Lead, on_delete=models.PROTECT, related_name="conversations"
    )
    # Галочка «Отслеживать»: расширение само передаёт новые сообщения чата.
    tracking = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "source", "external_id"],
                name="crm_unique_conversation",
            )
        ]


class ImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="imports"
    )
    token = models.ForeignKey(ExtensionToken, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    imported_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    received = models.PositiveIntegerField()
    created = models.PositiveIntegerField()
    history_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["token", "idempotency_key"], name="crm_unique_import"
            )
        ]


class Message(models.Model):
    class Direction(models.TextChoices):
        INCOMING = "in", "Входящее"
        OUTGOING = "out", "Исходящее"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT)
    external_id = models.CharField(max_length=200, blank=True)
    fingerprint = models.CharField(max_length=64)
    direction = models.CharField(max_length=3, choices=Direction.choices)
    author = models.CharField(max_length=200, blank=True)
    sent_at = models.DateTimeField(null=True)
    text = models.TextField(blank=True)
    has_attachment = models.BooleanField(default=False)
    # Порядок на странице: у вложений часто нет времени отправки.
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "fingerprint"], name="crm_unique_message"
            )
        ]
        indexes = [models.Index(fields=["conversation", "sent_at"])]
