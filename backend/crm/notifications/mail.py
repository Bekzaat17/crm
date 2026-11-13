from crm.core.mail import LinkEmail

from .models import Channel
from .services import enqueue


class OutboxMailer:
    """Mailer, который ставит письмо в очередь вместо отправки в запросе."""

    def send(self, email: LinkEmail) -> None:
        enqueue(
            channel=Channel.EMAIL,
            kind=email.page,
            dedup_key=email.key or f"email:{email.to}:{email.url}",
            subject=email.subject,
            body=email.body,
            address=email.to,
        )
