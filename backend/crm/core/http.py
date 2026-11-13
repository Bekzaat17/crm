import json
import logging
import smtplib
from functools import wraps

from django.db import IntegrityError
from django.http import JsonResponse

from .errors import ApiError

logger = logging.getLogger(__name__)


def _read_payload(request):
    if request.method != "POST":
        return {}
    if request.content_type != "application/json":
        raise ApiError("Ожидается JSON-запрос.", 415)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError("Некорректный JSON-запрос.")
    if not isinstance(payload, dict):
        raise ApiError("Ожидается объект JSON.")
    return payload


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
            except (smtplib.SMTPException, OSError):
                logger.warning("Сервис отправки почты недоступен")
                return JsonResponse(
                    {"error": "Не удалось отправить письмо. Попробуйте позже."},
                    status=503,
                )

        return wrapped

    return decorate
