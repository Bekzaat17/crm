import json
from functools import wraps

from django.db import IntegrityError
from django.http import JsonResponse

from .errors import ApiError


def parse_json_object(raw):
    """JSON-объект из тела запроса; любые ошибки разбора — 400."""
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise ApiError("Некорректный JSON-запрос.")
    if not isinstance(payload, dict):
        raise ApiError("Ожидается объект JSON.")
    return payload


def _read_payload(request):
    if request.method != "POST":
        return {}
    if request.content_type != "application/json":
        raise ApiError("Ожидается JSON-запрос.", 415)
    return parse_json_object(request.body)


def endpoint(methods, authenticated=False):
    """Общая проверка метода, сессии и JSON; ошибки операций → JSON-ответ."""

    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                response = JsonResponse(
                    {"error": "Метод не поддерживается."}, status=405
                )
                response["Allow"] = ", ".join(methods)
                return response
            if authenticated and not request.user.is_authenticated:
                return JsonResponse({"error": "Войдите в аккаунт."}, status=401)
            try:
                request.payload = _read_payload(request)
                return view(request, *args, **kwargs)
            except ApiError as exc:
                return JsonResponse({"error": exc.message}, status=exc.status)
            except IntegrityError:
                return JsonResponse(
                    {
                        "error": "Данные уже изменены. Обновите страницу и повторите действие."
                    },
                    status=409,
                )

        return wrapped

    return decorate
