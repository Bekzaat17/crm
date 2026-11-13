"""Постановка сообщений в очередь и доступные пользователю каналы."""

from django.conf import settings
from django.utils import timezone

from crm.core.crypto import encrypt
from crm.core.errors import ApiError

from .models import (
    Channel,
    NotificationPreference,
    OutboundMessage,
    PushSubscription,
    TelegramLink,
)
from .webpush import validate_endpoint


def enqueue(*, channel, kind, dedup_key, subject, body, url="", user=None, address=""):
    """Сообщение с тем же ключом заменяется и снова ставится в очередь."""
    message, _ = OutboundMessage.objects.update_or_create(
        dedup_key=dedup_key,
        defaults=dict(
            channel=channel,
            kind=kind,
            user=user,
            address=address,
            subject=encrypt(subject),
            body=encrypt(body),
            url=url,
            status=OutboundMessage.Status.PENDING,
            attempts=0,
            next_attempt_at=timezone.now(),
            lease_id=None,
            lease_until=None,
            last_error="",
            sent_at=None,
        ),
    )
    return message


def telegram_configured():
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_USERNAME)


def webpush_configured():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def preferences(user):
    return NotificationPreference.objects.filter(user=user).first() or (
        NotificationPreference(user=user)
    )


def enabled_channels(user):
    """Каналы, по которым напоминание реально может дойти до пользователя."""
    prefs = preferences(user)
    channels = []
    if prefs.email:
        channels.append(Channel.EMAIL)
    if (
        prefs.telegram
        and telegram_configured()
        and TelegramLink.objects.filter(user=user, is_blocked=False).exists()
    ):
        channels.append(Channel.TELEGRAM)
    if (
        prefs.webpush
        and webpush_configured()
        and PushSubscription.objects.filter(user=user).exists()
    ):
        channels.append(Channel.WEBPUSH)
    return channels


FLAGS = ("email", "telegram", "webpush")
MAX_SUBSCRIPTIONS = 10


def update_preferences(user, data):
    values = {}
    for flag in FLAGS:
        if flag in data:
            if not isinstance(data[flag], bool):
                raise ApiError("Некорректное значение настройки уведомлений.")
            values[flag] = data[flag]
    NotificationPreference.objects.update_or_create(user=user, defaults=values)


def _subscription_key(value, length):
    if not (isinstance(value, str) and 0 < len(value) <= length):
        raise ApiError("Некорректная подписка на уведомления.")
    return value


def subscribe_push(user, data):
    if not webpush_configured():
        raise ApiError("Уведомления браузера не настроены на сервере CRM.", 503)
    endpoint = validate_endpoint(data.get("endpoint"))
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    # Один браузер — одна подписка; при смене аккаунта она переходит новому.
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": user,
            "p256dh": _subscription_key(keys.get("p256dh"), 200),
            "auth": _subscription_key(keys.get("auth"), 100),
        },
    )
    # Не больше MAX_SUBSCRIPTIONS устройств: старые подписки удаляются.
    stale = PushSubscription.objects.filter(user=user).order_by("-created_at")[
        MAX_SUBSCRIPTIONS:
    ]
    PushSubscription.objects.filter(pk__in=[s.pk for s in stale]).delete()


def unsubscribe_push(user, endpoint):
    if isinstance(endpoint, str):
        PushSubscription.objects.filter(user=user, endpoint=endpoint).delete()
