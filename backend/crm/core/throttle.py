from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .errors import ApiError
from .models import RateLimitBucket
from .tokens import digest


def throttle(scope, identity, limit, seconds=3600):
    # Счётчик общий для процессов приложения; адрес прокси из заголовков не доверяем.
    now = timezone.now()
    key = digest(f"{scope}:{identity}")
    with transaction.atomic():
        bucket, _ = RateLimitBucket.objects.get_or_create(
            key=key, defaults={"started_at": now}
        )
        bucket = RateLimitBucket.objects.select_for_update().get(pk=bucket.pk)
        if bucket.started_at <= now - timedelta(seconds=seconds):
            bucket.started_at, bucket.count = now, 0
        if bucket.count >= limit:
            raise ApiError("Слишком много попыток. Попробуйте позже.", 429)
        bucket.count += 1
        bucket.save(update_fields=["started_at", "count"])


def client_throttle(request, scope, limit=20):
    """Ограничение по адресу непосредственного соединения (без proxy-заголовков)."""
    throttle(scope, request.META.get("REMOTE_ADDR", "unknown"), limit, 900)
