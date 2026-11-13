"""Каналы доставки (Strategy). Канал отправляет одно сообщение и сообщает,
можно ли повторить попытку. Выбор канала — фабрика channel_for()."""

import smtplib
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.core.mail import send_mail

from crm.core.errors import ApiError

from .models import OutboundMessage, PushSubscription, TelegramLink
from .services import telegram_configured, webpush_configured
from .telegram import TelegramClient, TelegramError, default_client
from .webpush import PushError, PushSender, VapidSender, validate_endpoint


@dataclass(frozen=True)
class Content:
    subject: str
    body: str
    url: str

    @property
    def absolute_url(self):
        return f"{settings.FRONTEND_URL}{self.url}" if self.url else ""


class DeliveryError(Exception):
    def __init__(self, code, retryable=True, retry_after=0):
        super().__init__(code)
        self.code, self.retryable, self.retry_after = code, retryable, retry_after


class DeliveryChannel(Protocol):
    def send(self, message: OutboundMessage, content: Content) -> None: ...


class EmailChannel:
    def send(self, message, content):
        recipient = message.address or (message.user.email if message.user else "")
        try:
            send_mail(
                content.subject, content.body, settings.DEFAULT_FROM_EMAIL, [recipient]
            )
        except (smtplib.SMTPException, OSError):
            raise DeliveryError("smtp_unavailable") from None


class TelegramChannel:
    def __init__(self, client: TelegramClient | None = None):
        self.client = client

    def send(self, message, content):
        client = self.client or default_client()
        if client is None or not telegram_configured():
            raise DeliveryError("channel_disabled", retryable=False)
        link = TelegramLink.objects.filter(user=message.user).first()
        if not link or link.is_blocked:
            raise DeliveryError("not_linked", retryable=False)
        text = "\n".join(
            part
            for part in (content.subject, content.body, content.absolute_url)
            if part
        )
        try:
            client.send_message(link.chat_id, text[:4000])
        except TelegramError as exc:
            if exc.status == 403:
                TelegramLink.objects.filter(pk=link.pk).update(is_blocked=True)
                raise DeliveryError("blocked_by_user", retryable=False) from None
            if exc.status == 429 or exc.status >= 500 or exc.status == 0:
                raise DeliveryError(exc.code, retry_after=exc.retry_after) from None
            raise DeliveryError(exc.code, retryable=False) from None


class WebPushChannel:
    """Отправка на все подписки пользователя; устаревшие подписки удаляются."""

    def __init__(self, sender: PushSender | None = None):
        self.sender = sender

    def send(self, message, content):
        if not webpush_configured():
            raise DeliveryError("channel_disabled", retryable=False)
        sender = self.sender or VapidSender()
        subscriptions = list(PushSubscription.objects.filter(user=message.user))
        if not subscriptions:
            raise DeliveryError("no_subscriptions", retryable=False)
        payload = {
            "title": content.subject,
            "body": content.body,
            "url": content.url,
            "tag": str(message.id),
        }
        delivered, retryable = 0, False
        for subscription in subscriptions:
            try:
                validate_endpoint(subscription.endpoint)
                sender.send(subscription, payload, ttl=3600)
                delivered += 1
            except ApiError:
                subscription.delete()
            except PushError as exc:
                if exc.status in (404, 410):
                    subscription.delete()
                elif exc.status in (0, 429) or exc.status >= 500:
                    retryable = True
        if not delivered:
            raise DeliveryError("push_failed", retryable=retryable)


def default_channels() -> dict[str, DeliveryChannel]:
    return {
        "email": EmailChannel(),
        "telegram": TelegramChannel(),
        "webpush": WebPushChannel(),
    }


def channel_for(name, channels=None) -> DeliveryChannel:
    registry = channels or default_channels()
    if name not in registry:
        raise DeliveryError("unknown_channel", retryable=False)
    return registry[name]
