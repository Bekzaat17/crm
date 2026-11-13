"""Импорт выбранного фрагмента переписки в обращение.

Повтор с тем же idempotency_key возвращает прежний результат. Сообщения
сопоставляются по внешнему идентификатору, а без него — по отпечатку
(направление, автор, время, текст и порядковый номер одинаковых сообщений
во фрагменте), поэтому одинаковый текст сам по себе не склеивает сообщения.
"""

from collections import Counter

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from crm.core.errors import ApiError
from crm.core.tokens import digest
from crm.core.validation import clean_text, identifier
from crm.sales.models import LeadActivity
from crm.sales.selectors import find_lead

from .models import Conversation, ImportBatch, Message, Source

MAX_MESSAGES = 500
MAX_TEXT = 10000


def _text(value, max_length, label):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > max_length:
        raise ApiError(f"Поле «{label}»: не более {max_length} символов.")
    return value.strip()


def _sent_at(value):
    if value in (None, ""):
        return None
    try:
        parsed = parse_datetime(value) if isinstance(value, str) else None
    except ValueError:
        parsed = None
    if parsed is None or timezone.is_naive(parsed):
        raise ApiError("Время сообщения нужно передать с часовым поясом.")
    return parsed


def clean_messages(raw):
    if not isinstance(raw, list) or not raw:
        raise ApiError("Выберите хотя бы одно сообщение.")
    if len(raw) > MAX_MESSAGES:
        raise ApiError(f"За один раз можно передать до {MAX_MESSAGES} сообщений.")
    seen = Counter()
    messages = []
    for item in raw:
        if not isinstance(item, dict):
            raise ApiError("Некорректное сообщение.")
        direction = item.get("direction")
        if direction not in Message.Direction.values:
            raise ApiError("Укажите направление сообщения.")
        message = dict(
            external_id=_text(item.get("external_id"), 200, "Идентификатор"),
            direction=direction,
            author=_text(item.get("author"), 200, "Автор"),
            sent_at=_sent_at(item.get("sent_at")),
            text=_text(item.get("text"), MAX_TEXT, "Текст"),
            has_attachment=item.get("has_attachment") is True,
        )
        if message["external_id"]:
            key = f"id:{message['external_id']}"
        else:
            base = "|".join(
                [
                    direction,
                    message["author"],
                    message["sent_at"].isoformat() if message["sent_at"] else "",
                    message["text"],
                ]
            )
            seen[base] += 1
            key = f"fp:{base}|{seen[base]}"
        message["fingerprint"] = digest(key)
        messages.append(message)
    return messages


def batch_result(batch):
    return {
        "conversation_id": str(batch.conversation_id),
        "lead_id": str(batch.conversation.lead_id),
        "received": batch.received,
        "created": batch.created,
        "duplicates": batch.received - batch.created,
    }


@transaction.atomic
def import_fragment(context, data):
    member, token = context.member, context.token
    key = identifier(data.get("idempotency_key"))
    existing = (
        ImportBatch.objects.select_related("conversation")
        .filter(token=token, idempotency_key=key)
        .first()
    )
    conversation_data = data.get("conversation") or {}
    external_id = clean_text(
        conversation_data.get("external_id"), "Идентификатор диалога", 200
    )
    if existing:
        if existing.conversation.external_id != external_id:
            raise ApiError(
                "Этот ключ повтора уже использован для другого диалога.", 409
            )
        return batch_result(existing), False
    source = data.get("source")
    if source not in Source.values:
        raise ApiError("Источник должен быть WhatsApp, Telegram или Instagram.")
    # Обращение ищется в области доступа сотрудника, которому выдан ключ.
    lead = find_lead(member, identifier(data.get("lead_id")), lock=True)
    messages = clean_messages(data.get("messages"))
    conversation, _ = Conversation.objects.select_for_update().get_or_create(
        organization_id=member.organization_id,
        source=source,
        external_id=external_id,
        defaults=dict(
            title=clean_text(conversation_data.get("title"), "Название диалога", 200),
            lead=lead,
            created_by=member.user,
        ),
    )
    if conversation.lead_id != lead.id:
        raise ApiError("Этот диалог уже привязан к другому обращению.", 409)
    batch = ImportBatch.objects.create(
        conversation=conversation,
        token=token,
        idempotency_key=key,
        imported_by=member.user,
        received=len(messages),
        created=0,
        history_note=_text(data.get("history_note"), 300, "Примечание"),
    )
    known = set(
        Message.objects.filter(
            conversation=conversation,
            fingerprint__in=[m["fingerprint"] for m in messages],
        ).values_list("fingerprint", flat=True)
    )
    fresh = [
        (position, m)
        for position, m in enumerate(messages)
        if m["fingerprint"] not in known
    ]
    Message.objects.bulk_create(
        Message(conversation=conversation, batch=batch, position=position, **m)
        for position, m in fresh
    )
    batch.created = len(fresh)
    batch.save(update_fields=["created"])
    conversation.save(update_fields=["updated_at"])
    LeadActivity.objects.create(
        lead=lead,
        actor=member.user,
        kind="import",
        text=(
            f"Импортирована переписка {Source(source).label}: "
            f"новых сообщений {len(fresh)} из {len(messages)}"
        ),
    )
    return batch_result(batch), True
