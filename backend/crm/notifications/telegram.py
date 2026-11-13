"""Клиент Telegram Bot API. Токен входит в путь запроса, поэтому ошибки
транспорта заменяются собственным исключением без текста запроса."""

import http.client
import json
import ssl
from typing import Protocol

from django.conf import settings

HOST = "api.telegram.org"


class TelegramError(Exception):
    def __init__(self, status=0, code="network_error", retry_after=0):
        super().__init__(code)
        self.status, self.code, self.retry_after = status, code, retry_after


class TelegramClient(Protocol):
    def send_message(self, chat_id: int, text: str) -> None: ...

    def get_updates(self, offset: int, timeout: int) -> list[dict]: ...


class BotApiClient:
    def __init__(self, token: str):
        self._token = token

    def _call(self, method, payload, timeout=15):
        connection = http.client.HTTPSConnection(
            HOST, timeout=timeout, context=ssl.create_default_context()
        )
        try:
            connection.request(
                "POST",
                f"/bot{self._token}/{method}",
                body=json.dumps(payload, ensure_ascii=False).encode(),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            data = json.loads(response.read(1_000_000) or b"{}")
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise TelegramError(code=type(exc).__name__) from None
        finally:
            connection.close()
        if not isinstance(data, dict) or not data.get("ok"):
            parameters = data.get("parameters", {}) if isinstance(data, dict) else {}
            raise TelegramError(
                response.status,
                f"http_{response.status}",
                int(parameters.get("retry_after", 0) or 0),
            )
        return data.get("result")

    def send_message(self, chat_id, text):
        self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "link_preview_options": {"is_disabled": True},
            },
        )

    def get_updates(self, offset, timeout):
        return self._call(
            "getUpdates",
            {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
            timeout=timeout + 10,
        )


def default_client() -> TelegramClient | None:
    token = settings.TELEGRAM_BOT_TOKEN
    return BotApiClient(token) if token else None
