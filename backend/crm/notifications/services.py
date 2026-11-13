"""Постановка сообщений в очередь и доступные пользователю каналы."""

from django.conf import settings
from django.utils import timezone

from crm.core.crypto import encrypt

from .models import (
    Channel,
    NotificationPreference,
    OutboundMessage,
    PushSubscription,
    TelegramLink,
)


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
