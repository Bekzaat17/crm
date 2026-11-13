from django.utils import timezone
from django.utils.dateparse import parse_date

from crm.core.errors import ApiError
from crm.core.validation import clean_text, optional


def birth_date(raw):
    if raw is None or raw == "":
        return None
    try:
        value = parse_date(raw) if isinstance(raw, str) else None
    except ValueError:
        value = None
    if value is None or value > timezone.localdate():
        raise ApiError("Укажите корректную дату рождения, не позднее сегодняшнего дня.")
    return value


def client_fields(data):
    return dict(
        name=clean_text(data.get("name"), "ФИО клиента", 240),
        phone=optional(data, "phone", 40),
        city=optional(data, "city", 120),
        notes=optional(data, "notes", 5000),
        date_of_birth=birth_date(data.get("date_of_birth")),
    )
