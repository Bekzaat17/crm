from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token

from crm.core.errors import ApiError
from crm.core.http import endpoint
from crm.core.throttle import client_throttle, throttle
from crm.core.validation import clean_email, clean_text

from . import services
from .serializers import session_data


def csrf_failure(request, reason=""):
    return JsonResponse(
        {"error": "Защита сессии: обновите страницу и повторите действие."}, status=403
    )


def auth_response(request):
    return JsonResponse(
        {**session_data(request.user), "csrf_token": get_token(request)}
    )


@endpoint(["GET"])
def session(request):
    return auth_response(request)


@endpoint(["POST"])
def register(request):
    client_throttle(request, "register-ip", 10)
    services.request_registration(request.payload)
    return JsonResponse(
        {
            "message": "Если адрес доступен для регистрации, мы отправили письмо. Проверьте почту. Если аккаунт уже есть — войдите."
        },
        status=202,
    )


@endpoint(["POST"])
def verify(request):
    client_throttle(request, "verify-ip", 30)
    token = clean_text(request.payload.get("token"), "Код подтверждения", 256)
    login(request, services.confirm_registration(token))
    return auth_response(request)


@endpoint(["POST"])
def sign_in(request):
    client_throttle(request, "login-ip", 60)
    email = clean_email(request.payload.get("email"))
    throttle("login-email", email, 10, 900)
    password = request.payload.get("password")
    if not isinstance(password, str) or len(password) > 128:
        raise ApiError("Неверная почта или пароль.", 401)
    user = authenticate(request, email=email, password=password)
    if not user:
        raise ApiError("Неверная почта или пароль.", 401)
    login(request, user)
    return auth_response(request)


@endpoint(["POST"], authenticated=True)
def sign_out(request):
    logout(request)
    return JsonResponse({"message": "Вы вышли из аккаунта."})


@endpoint(["POST"])
def forgot_password(request):
    client_throttle(request, "reset-ip", 15)
    services.request_password_reset(request.payload.get("email"))
    return JsonResponse(
        {"message": "Если аккаунт существует, письмо для восстановления отправлено."},
        status=202,
    )


@endpoint(["POST"])
def reset_password(request):
    client_throttle(request, "reset-confirm-ip", 20)
    services.reset_password(request.payload)
    return JsonResponse({"message": "Пароль изменён. Войдите с новым паролем."})
