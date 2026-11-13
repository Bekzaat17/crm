from django.http import JsonResponse

from crm.core.http import endpoint
from crm.core.throttle import throttle

from . import services, telegram_link
from .serializers import notification_state


@endpoint(["GET", "POST"], authenticated=True)
def notification_settings(request):
    if request.method == "POST":
        services.update_preferences(request.user, request.payload)
    return JsonResponse(notification_state(request.user))


@endpoint(["POST"], authenticated=True)
def telegram_link_create(request):
    throttle("telegram-link", str(request.user.pk), 10)
    url, expires_at = telegram_link.create_link(request.user)
    return JsonResponse({"url": url, "expires_at": expires_at.isoformat()})


@endpoint(["POST"], authenticated=True)
def telegram_unlink(request):
    telegram_link.unlink(request.user)
    return JsonResponse(notification_state(request.user))


@endpoint(["POST"], authenticated=True)
def push_subscribe(request):
    throttle("push-subscribe", str(request.user.pk), 30)
    services.subscribe_push(request.user, request.payload)
    return JsonResponse(notification_state(request.user), status=201)


@endpoint(["POST"], authenticated=True)
def push_unsubscribe(request):
    services.unsubscribe_push(request.user, request.payload.get("endpoint"))
    return JsonResponse(notification_state(request.user))
