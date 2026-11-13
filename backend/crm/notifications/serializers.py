from django.conf import settings

from .models import PushSubscription, TelegramLink
from .services import FLAGS, preferences, telegram_configured, webpush_configured


def notification_state(user):
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
