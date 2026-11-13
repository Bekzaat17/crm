from uuid import UUID

from django.utils import timezone
from django.utils.dateparse import parse_date

from crm.services import ApiError, clean_text


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


def client_fields(data):
    raw = data.get("date_of_birth")
    birthday = None
    if raw is not None and raw != "":
        try:
            birthday = parse_date(raw) if isinstance(raw, str) else None
        except ValueError:
            birthday = None
        if birthday is None or birthday > timezone.localdate():
            raise ApiError(
                "Укажите корректную дату рождения, не позднее сегодняшнего дня."
            )
    return dict(
        name=clean_text(data.get("name"), "ФИО клиента", 240),
        phone=optional(data, "phone", 40),
        city=optional(data, "city", 120),
        notes=optional(data, "notes", 5000),
        date_of_birth=birthday,
    )
