"""Web Push. Адрес подписки приходит из браузера, поэтому разрешены только
известные push-сервисы (защита от SSRF), без прокси окружения и редиректов."""

import json
from typing import Protocol
from urllib.parse import urlsplit

from django.conf import settings

from crm.core.errors import ApiError

PUSH_HOSTS = (
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "web.push.apple.com",
)
PUSH_HOST_SUFFIXES = (".push.apple.com", ".notify.windows.com")


def validate_endpoint(value):
    if not isinstance(value, str) or len(value) > 500:
        raise ApiError("Некорректная подписка на уведомления.")
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    allowed = host in PUSH_HOSTS or host.endswith(PUSH_HOST_SUFFIXES)
    if parts.scheme != "https" or parts.port not in (None, 443) or not allowed:
        raise ApiError("Этот браузер использует неподдерживаемый сервис уведомлений.")
    return value


class PushError(Exception):
    def __init__(self, status=0):
        super().__init__(f"push_{status}")
        self.status = status


class PushSender(Protocol):
    def send(self, subscription, payload: dict, ttl: int) -> None: ...


class VapidSender:
    def send(self, subscription, payload, ttl):
        import requests
        from pywebpush import WebPushException, webpush

        session = requests.Session()
        session.trust_env = False
        session.max_redirects = 0
        try:
            webpush(
                {
                    "endpoint": validate_endpoint(subscription.endpoint),
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                ttl=ttl,
                timeout=10,
                headers={"Urgency": "high"},
                requests_session=session,
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else 0
            raise PushError(status) from None
        except (requests.RequestException, OSError, ValueError):
            raise PushError(0) from None
        finally:
            session.close()
