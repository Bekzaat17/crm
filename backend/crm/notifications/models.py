import uuid

from django.db import models
from django.utils import timezone

from crm.accounts.models import User


class Channel(models.TextChoices):
    EMAIL = "email", "Почта"
    TELEGRAM = "telegram", "Telegram"
    WEBPUSH = "webpush", "Уведомления браузера"


class OutboundMessage(models.Model):
    """Сообщение в очереди отправки (Transactional Outbox).

    Тема и текст зашифрованы: письма содержат действующие ссылки. После
    отправки или отмены содержимое стирается.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "В очереди"
        SENDING = "sending", "Отправляется"
        RETRY = "retry", "Ожидает повтора"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Не отправлено"
        CANCELLED = "cancelled", "Отменено"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    address = models.EmailField(blank=True)
    kind = models.CharField(max_length=40)
    dedup_key = models.CharField(max_length=200, unique=True)
    subject = models.TextField(blank=True)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_id = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=120, blank=True)
    sent_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt_at"])]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(user__isnull=True, address=""),
                name="crm_message_has_recipient",
            )
        ]


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="notification_preference"
    )
    email = models.BooleanField(default=False)
    telegram = models.BooleanField(default=True)
    webpush = models.BooleanField(default=True)


class TelegramLink(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="telegram_link"
    )
    chat_id = models.BigIntegerField(unique=True)
    is_blocked = models.BooleanField(default=False)
    linked_at = models.DateTimeField(auto_now_add=True)


class TelegramLinkToken(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)


class TelegramCursor(models.Model):
    """Последний обработанный update_id: повторный запуск не обрабатывает его снова."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    offset = models.BigIntegerField(default=0)


class PushSubscription(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)


class ReminderDispatch(models.Model):
    """Факт постановки напоминания: одно напоминание на событие и срок."""

    kind = models.CharField(max_length=20)
    object_id = models.UUIDField()
    due_at = models.DateTimeField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "object_id", "due_at", "user"],
                name="crm_unique_reminder",
            )
        ]
