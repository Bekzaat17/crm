"""Transactional Outbox: БД — очередь, HTTPS-адаптер подменяется в тестах."""

import http.client
import random
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from crm.models import AdmissionTransfer, DeliveryAttempt, LeadActivity
from crm.services import ApiError

from .secrets import decrypt
from .transport import HTTPSClient, Transport

MAX_ATTEMPTS = 8
LEASE_SECONDS = 120


@transaction.atomic
def claim_next():
    now = timezone.now()
    eligible = Q(status__in=["pending", "retry"], next_attempt_at__lte=now) | Q(
        status="sending", lease_until__lte=now
    )
    job = (
        AdmissionTransfer.objects.select_for_update(skip_locked=True)
        .filter(eligible)
        .order_by("next_attempt_at", "id")
        .first()
    )
    if job is None:
        return None
    if job.cycle_attempts >= MAX_ATTEMPTS:
        job.status = "failed"
        job.last_error = "attempts_exhausted"
        job.save()
        return None
    job.status = "sending"
    job.lease_id = uuid.uuid4()
    job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
    job.attempt_count += 1
    job.cycle_attempts += 1
    job.save()
    DeliveryAttempt.objects.create(transfer=job, number=job.attempt_count)
    return job


def classify(reply, operation_id):
    if reply.status in (200, 201):
        resident_id = reply.data.get("resident_id")
        if (
            reply.data.get("external_admission_id") == str(operation_id)
            and reply.data.get("status") == "delivered"
            and isinstance(resident_id, (int, str))
            and not isinstance(resident_id, bool)
            and len(str(resident_id)) <= 100
            and str(resident_id).isdecimal()
            and int(resident_id) > 0
        ):
            return "delivered", "", str(resident_id)
        return "retry", "invalid_response", ""
    if reply.status == 409:
        return "conflict", "remote_conflict", ""
    if reply.status in (401, 403):
        return "blocked", "remote_access_denied", ""
    if reply.status == 429 or reply.status >= 500:
        return "retry", f"http_{reply.status}", ""
    if 300 <= reply.status < 400:
        return "blocked", "redirect_forbidden", ""
    return "failed", f"http_{reply.status}", ""


@transaction.atomic
def finish(job, status, error, http_status=None, resident_id="", retry_after=0):
    current = (
        AdmissionTransfer.objects.select_for_update()
        .filter(pk=job.id, status="sending", lease_id=job.lease_id)
        .first()
    )
    if current is None:
        return
    now = timezone.now()
    DeliveryAttempt.objects.filter(transfer=current, number=job.attempt_count).update(
        finished_at=now, outcome=error or status, http_status=http_status
    )
    if status == "retry" and current.cycle_attempts >= MAX_ATTEMPTS:
        status = "failed"
    current.status = status
    current.last_error = error
    current.lease_until = None
    current.lease_id = None
    if status == "delivered":
        current.resident_id = resident_id
        current.delivered_at = now
        # Доставка и факт поступления различаются: этап менеджер меняет отдельно.
        LeadActivity.objects.create(
            lead=current.lead,
            actor=current.confirmed_by,
            kind="transfer",
            text=f"Центр «{current.center.name}» подтвердил передачу. Резидент №{resident_id}.",
        )
    elif status == "retry":
        delay = max(
            retry_after,
            min(3600, 30 * 2 ** (current.cycle_attempts - 1)) + random.randint(0, 15),
        )
        current.next_attempt_at = now + timedelta(seconds=delay)
    current.save()


def deliver_one(transport: Transport | None = None):
    job = claim_next()
    if job is None:
        return False
    center = job.center
    if not center.is_active or not center.verified_at:
        finish(job, "blocked", "connection_inactive")
        return True
    try:
        reply = (transport or HTTPSClient()).request(
            center.domain,
            decrypt(center.encrypted_key),
            "/crm/create",
            job.payload,
            str(job.id),
        )
        status, error, resident_id = classify(reply, job.id)
        finish(job, status, error, reply.status, resident_id, reply.retry_after)
    except ApiError:
        finish(job, "blocked", "connection_configuration")
    except ValueError:
        finish(job, "blocked", "unsafe_destination")
    except (OSError, TimeoutError, http.client.HTTPException):
        finish(job, "retry", "network_error")
    return True
