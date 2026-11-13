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


def optional(data, key, length):
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > length:
        raise ApiError(f"Поле {key}: не более {length} символов.")
    return value.strip()


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
