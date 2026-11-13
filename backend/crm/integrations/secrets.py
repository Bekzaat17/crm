from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from crm.core.errors import ApiError


def cipher():
    try:
        return Fernet(settings.INTEGRATION_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        raise ApiError("Не настроен ключ шифрования подключений CRM.", 503)


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken:
        raise ApiError(
            "Не удалось открыть ключ подключения. Проверьте конфигурацию CRM.", 503
        )
