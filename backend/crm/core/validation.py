"""Преобразование и проверка входных полей. Не зависит от моделей."""

from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .errors import ApiError


def clean_text(value, label, max_length):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_length
    ):
        raise ApiError(f"Заполните поле «{label}» (не более {max_length} символов).")
    return value.strip()


def clean_email(value):
    email = clean_text(value, "Электронная почта", 254).lower()
    try:
        validate_email(email)
    except ValidationError:
        raise ApiError("Укажите корректный адрес электронной почты.")
    return email


def identifier(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ApiError("Некорректный идентификатор.")


FIELD_LABELS = {
    "phone": "Телефон",
    "city": "Город",
    "notes": "Заметки",
    "source": "Источник",
    "refusal_reason": "Причина отказа",
}


def optional(data, key, length, label=None):
    """Необязательная строка: отсутствие и null — пустая строка."""
    value = data.get(key)
    if value is None:
        return ""
    title = label or FIELD_LABELS.get(key, key)
    if not isinstance(value, str):
        raise ApiError(f"Поле «{title}» должно быть строкой.")
    value = value.strip()
    if len(value) > length:
        raise ApiError(f"Поле «{title}»: не более {length} символов.")
    return value


def require_version(obj, data, message):
    """Optimistic locking: клиент присылает прочитанную version."""
    if data.get("version") != obj.version:
        raise ApiError(message, 409)


def unique_name(name, existing, message):
    """Название без учёта регистра (casefold в Python: SQLite не сравнивает
    кириллицу без учёта регистра)."""
    if any(other.casefold() == name.casefold() for other in existing):
        raise ApiError(message, 409)
    return name


def aware_datetime(value, message):
    """Дата и время строго с часовым поясом, иначе ApiError(message)."""
    try:
        parsed = parse_datetime(value) if isinstance(value, str) else None
    except ValueError:
        parsed = None
    if parsed is None or timezone.is_naive(parsed):
        raise ApiError(message)
    return parsed


def optional_aware_datetime(value, message):
    """Пустое значение означает отсутствие даты."""
    if value is None or value == "":
        return None
    return aware_datetime(value, message)
