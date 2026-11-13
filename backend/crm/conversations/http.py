"""HTTP-обёртка API расширения.

Доступ только по Bearer-ключу: cookie сессии на этих маршрутах не
используются, поэтому CSRF-защита здесь не применяется. Тело запроса больше
общего лимита Django и читается потоком с собственным ограничением.
"""

import json
from functools import wraps

from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from crm.core.errors import ApiError
from crm.core.throttle import throttle

from .tokens import authenticate

MAX_BODY = 2 * 1024 * 1024


def _payload(request):
    if request.method != "POST":
        return {}
    if request.content_type != "application/json":
        raise ApiError("Ожидается JSON-запрос.", 415)
    raw = request.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ApiError("Слишком большой фрагмент переписки.", 413)
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError("Некорректный JSON-запрос.")
    if not isinstance(payload, dict):
        raise ApiError("Ожидается объект JSON.")
    return payload


def extension_endpoint(methods):
    def decorate(view):
        @csrf_exempt
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return JsonResponse({"error": "Метод не поддерживается."}, status=405)
            try:
                context = authenticate(request.headers.get("Authorization"))
                throttle("extension", str(context.token.pk), 600, 3600)
                request.extension = context
                request.payload = _payload(request)
                return view(request, *args, **kwargs)
            except ApiError as exc:
                return JsonResponse({"error": exc.message}, status=exc.status)
            except IntegrityError:
                return JsonResponse(
                    {"error": "Импорт уже выполняется. Повторите запрос."}, status=409
                )

        return wrapped

    return decorate
