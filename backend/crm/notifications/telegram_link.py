"""Привязка Telegram: одноразовая ссылка t.me/<бот>?start=<токен> на 15 минут.
Токен хранится только хешем; чат привязывается к пользователю, открывшему ссылку."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from crm.core.errors import ApiError
from crm.core.tokens import digest, new_token

from .models import TelegramCursor, TelegramLink, TelegramLinkToken
from .services import telegram_configured
from .telegram import TelegramClient, TelegramError

LINK_TTL = timedelta(minutes=15)
REPLIES = {
    "linked": "Уведомления RehubPro CRM подключены. Отключить: /stop",
    "invalid": "Ссылка недействительна или устарела. Получите новую в настройках CRM.",
    "stopped": "Уведомления отключены. Подключить снова можно в настройках CRM.",
}


def create_link(user):
    if not telegram_configured():
        raise ApiError("Telegram-бот не настроен на сервере CRM.", 503)
    token = new_token()
    expires_at = timezone.now() + LINK_TTL
    TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).delete()
    TelegramLinkToken.objects.create(
        user=user, token_hash=digest(token), expires_at=expires_at
    )
    url = f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}"
    return url, expires_at


def unlink(user):
    TelegramLink.objects.filter(user=user).delete()


@transaction.atomic
def bind_chat(token, chat_id):
    record = (
        TelegramLinkToken.objects.select_for_update()
        .filter(
            token_hash=digest(token),
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if record is None:
        return None
    record.used_at = timezone.now()
    record.save(update_fields=["used_at"])
    TelegramLink.objects.filter(chat_id=chat_id).exclude(user=record.user).delete()
    TelegramLink.objects.update_or_create(
        user=record.user, defaults={"chat_id": chat_id, "is_blocked": False}
    )
    return record.user


def handle_update(update, client: TelegramClient):
    """Обрабатывает только личные сообщения /start <токен> и /stop."""
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    text = message.get("text") or ""
    if chat.get("type") != "private" or not isinstance(chat.get("id"), int):
        return
    command, _, argument = text.strip().partition(" ")
    if command == "/start":
        user = bind_chat(argument.strip(), chat["id"]) if argument else None
        reply = REPLIES["linked"] if user else REPLIES["invalid"]
    elif command == "/stop":
        TelegramLink.objects.filter(chat_id=chat["id"]).update(is_blocked=True)
        reply = REPLIES["stopped"]
    else:
        return
    try:
        client.send_message(chat["id"], reply)
    except TelegramError:
        pass  # ответ боту не критичен: привязка уже сохранена


def poll_once(client: TelegramClient, timeout=25):
    cursor, _ = TelegramCursor.objects.get_or_create(pk=1)
    updates = client.get_updates(cursor.offset + 1 if cursor.offset else 0, timeout)
    for update in updates or []:
        update_id = update.get("update_id")
        if not isinstance(update_id, int) or update_id <= cursor.offset:
            continue
        handle_update(update, client)
        # Смещение сохраняется после каждого обновления: перезапуск не повторит его.
        cursor.offset = update_id
        cursor.save(update_fields=["offset"])
    return len(updates or [])
