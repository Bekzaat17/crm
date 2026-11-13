"""Письма со ссылками. Mailer — узкая зависимость, письмо — отдельный объект."""

from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail


@dataclass(frozen=True)
class LinkEmail:
    """Письмо с действующей ссылкой. Параметры передаются во фрагменте URL:
    фрагмент не уходит на сервер и не попадает в access log."""

    to: str
    subject: str
    message: str
    page: str
    params: dict = field(default_factory=dict)

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


class DjangoMailer:
    def send(self, email: LinkEmail) -> None:
        send_mail(email.subject, email.body, settings.DEFAULT_FROM_EMAIL, [email.to])


def default_mailer() -> Mailer:
    return DjangoMailer()
