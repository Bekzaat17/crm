import json
import logging
import smtplib
from functools import wraps

from django.db import IntegrityError
from django.http import JsonResponse

from . import services

logger = logging.getLogger(__name__)


def endpoint(methods, authenticated=False):
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
                request.payload = {}
                if request.method == "POST":
                    if request.content_type != "application/json":
                        raise services.ApiError("Ожидается JSON-запрос.", 415)
                    try:
                        request.payload = json.loads(request.body)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        raise services.ApiError("Некорректный JSON-запрос.")
                    if not isinstance(request.payload, dict):
                        raise services.ApiError("Ожидается объект JSON.")
                return view(request, *args, **kwargs)
            except services.ApiError as exc:
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
