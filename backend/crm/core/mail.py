"""Письма со ссылками. Mailer — узкая зависимость (по умолчанию очередь
писем, settings.CRM_MAILER), письмо — отдельный объект."""

from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlencode

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class LinkEmail:
    """Письмо с действующей ссылкой. Параметры передаются во фрагменте URL:
    фрагмент не уходит на сервер и не попадает в access log."""

    to: str
    subject: str
    message: str
    page: str
    params: dict = field(default_factory=dict)
    # Ключ дедупликации в очереди: новое письмо того же назначения заменяет старое.
    key: str = ""

    @property
    def url(self):
        return f"{settings.FRONTEND_URL}/{self.page}#{urlencode(self.params)}"

    @property
    def body(self):
        return (
            f"{self.message}\n\n{self.url}\n\n"
            "Если вы не запрашивали это письмо, проигнорируйте его."
        )


class Mailer(Protocol):
    def send(self, email: LinkEmail) -> None: ...


def default_mailer() -> Mailer:
    """Отправитель из настроек CRM_MAILER (по умолчанию — очередь писем)."""
    return import_string(settings.CRM_MAILER)()
