"""Исполнитель очереди сообщений."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from crm.core import outbox
from crm.core.crypto import decrypt
from crm.core.errors import ApiError

from .channels import Content, DeliveryError, channel_for
from .models import OutboundMessage

MAX_ATTEMPTS = 8
LEASE_SECONDS = 60
FINAL = (
    OutboundMessage.Status.SENT,
    OutboundMessage.Status.FAILED,
    OutboundMessage.Status.CANCELLED,
)


def _wipe(message):
    # Содержимое может включать действующие ссылки: после завершения не храним.
    message.subject = ""
    message.body = ""


@transaction.atomic
def claim_next():
    now = timezone.now()
    job = outbox.lock_next(OutboundMessage.objects, now)
    if job is None:
        return None
    if job.attempts >= MAX_ATTEMPTS:
        job.status = OutboundMessage.Status.FAILED
        job.last_error = "attempts_exhausted"
        outbox.release(job)
        _wipe(job)
        job.save()
        return None
    outbox.take_lease(job, LEASE_SECONDS, now)
    job.attempts += 1
    job.save()
    return job


@transaction.atomic
def finish(job, status, error="", retry_after=0):
    current = outbox.current_lease(OutboundMessage.objects, job)
    if current is None:
        return
    now = timezone.now()
    if status == "retry" and current.attempts >= MAX_ATTEMPTS:
        status = OutboundMessage.Status.FAILED
    current.status = status
    current.last_error = error
    outbox.release(current)
    if status == OutboundMessage.Status.SENT:
        current.sent_at = now
    if status in FINAL:
        _wipe(current)
    else:
        delay = outbox.backoff_seconds(current.attempts, retry_after)
        current.next_attempt_at = now + timedelta(seconds=delay)
    current.save()


def dispatch_one(channels=None):
    job = claim_next()
    if job is None:
        return False
    try:
        content = Content(decrypt(job.subject), decrypt(job.body), job.url)
        channel_for(job.channel, channels).send(job, content)
    except DeliveryError as exc:
        finish(job, "retry" if exc.retryable else "failed", exc.code, exc.retry_after)
    except ApiError:
        finish(job, "retry", "configuration")
    else:
        finish(job, OutboundMessage.Status.SENT)
    return True


def dispatch_all(channels=None, limit=1000):
    """Отправить всё готовое (тесты и разовый запуск)."""
    count = 0
    while count < limit and dispatch_one(channels):
        count += 1
    return count
