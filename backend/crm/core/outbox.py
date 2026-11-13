"""Общие механизмы очередей в БД (Transactional Outbox).

Запись очереди хранит status, next_attempt_at, lease_id и lease_until.
Исполнитель берёт запись с SKIP LOCKED и арендой; результат записывается
только при совпадении lease_id (fencing token), поэтому опоздавший
исполнитель не перезапишет результат нового.
"""

import random
import uuid
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

WAITING = ("pending", "retry")


def eligible(now):
    return Q(status__in=WAITING, next_attempt_at__lte=now) | Q(
        status="sending", lease_until__lte=now
    )


def lock_next(queryset, now=None):
    """Следующая готовая запись под блокировкой строки; вызывать в транзакции."""
    now = now or timezone.now()
    return (
        queryset.select_for_update(skip_locked=True)
        .filter(eligible(now))
        .order_by("next_attempt_at", "pk")
        .first()
    )


def take_lease(job, seconds, now=None):
    job.status = "sending"
    job.lease_id = uuid.uuid4()
    job.lease_until = (now or timezone.now()) + timedelta(seconds=seconds)


def release(job):
    job.lease_id = None
    job.lease_until = None


def current_lease(queryset, job):
    """Запись под блокировкой, если аренда исполнителя ещё действует."""
    return (
        queryset.select_for_update()
        .filter(pk=job.pk, status="sending", lease_id=job.lease_id)
        .first()
    )


def backoff_seconds(attempt, retry_after=0, cap=3600):
    """Экспоненциальная пауза со случайной добавкой и учётом Retry-After."""
    return max(
        retry_after, min(cap, 30 * 2 ** max(attempt - 1, 0)) + random.randint(0, 15)
    )
