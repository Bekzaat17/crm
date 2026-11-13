from crm.core.errors import ApiError
from crm.core.validation import clean_text

from .models import Source


def clean_source(value):
    if value not in Source.values:
        raise ApiError("Источник должен быть WhatsApp, Telegram или Instagram.")
    return value


def clean_external_id(value):
    return clean_text(value, "Идентификатор диалога", 200)
