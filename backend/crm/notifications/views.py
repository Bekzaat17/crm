from django.conf import settings
from django.http import JsonResponse

from crm.core.errors import ApiError
from crm.core.http import endpoint
from crm.core.throttle import throttle

from . import telegram_link
from .models import NotificationPreference, PushSubscription, TelegramLink
from .services import preferences, telegram_configured, webpush_configured
from .webpush import validate_endpoint

FLAGS = ("email", "telegram", "webpush")


def state(user):
    prefs = preferences(user)
    link = TelegramLink.objects.filter(user=user).first()
    return {
        "preferences": {flag: getattr(prefs, flag) for flag in FLAGS},
        "telegram": {
            "available": telegram_configured(),
            "linked": bool(link and not link.is_blocked),
            "blocked": bool(link and link.is_blocked),
        },
        "webpush": {
            "available": webpush_configured(),
            "public_key": settings.VAPID_PUBLIC_KEY if webpush_configured() else "",
            "subscriptions": PushSubscription.objects.filter(user=user).count(),
        },
    }


@endpoint(["GET", "POST"], authenticated=True)
def notification_settings(request):
    if request.method == "POST":
        values = {}
        for flag in FLAGS:
            if flag in request.payload:
                if not isinstance(request.payload[flag], bool):
                    raise ApiError("Некорректное значение настройки уведомлений.")
                values[flag] = request.payload[flag]
        NotificationPreference.objects.update_or_create(
            user=request.user, defaults=values
        )
    return JsonResponse(state(request.user))


@endpoint(["POST"], authenticated=True)
def telegram_link_create(request):
    throttle("telegram-link", str(request.user.pk), 10)
    url, expires_at = telegram_link.create_link(request.user)
    return JsonResponse({"url": url, "expires_at": expires_at.isoformat()})


@endpoint(["POST"], authenticated=True)
def telegram_unlink(request):
    telegram_link.unlink(request.user)
    return JsonResponse(state(request.user))


@endpoint(["POST"], authenticated=True)
def push_subscribe(request):
    if not webpush_configured():
        raise ApiError("Уведомления браузера не настроены на сервере CRM.", 503)
    throttle("push-subscribe", str(request.user.pk), 30)
    endpoint_url = validate_endpoint(request.payload.get("endpoint"))
    keys = request.payload.get("keys")
    if not isinstance(keys, dict):
        raise ApiError("Некорректная подписка на уведомления.")
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not (isinstance(p256dh, str) and 0 < len(p256dh) <= 200):
        raise ApiError("Некорректная подписка на уведомления.")
    if not (isinstance(auth, str) and 0 < len(auth) <= 100):
        raise ApiError("Некорректная подписка на уведомления.")
    # Один браузер — одна подписка; при смене аккаунта она переходит новому.
    PushSubscription.objects.update_or_create(
        endpoint=endpoint_url,
        defaults={"user": request.user, "p256dh": p256dh, "auth": auth},
    )
    return JsonResponse(state(request.user), status=201)


@endpoint(["POST"], authenticated=True)
def push_unsubscribe(request):
    endpoint_url = request.payload.get("endpoint")
    if isinstance(endpoint_url, str):
        PushSubscription.objects.filter(
            user=request.user, endpoint=endpoint_url
        ).delete()
    return JsonResponse(state(request.user))
