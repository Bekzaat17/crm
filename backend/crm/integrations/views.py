from django.http import JsonResponse

from crm.http import endpoint
from crm.models import RehubCenter
from crm.services import get_membership

from . import services
from .selectors import admin_membership, transfers_for


def transfer_data(transfer):
    return {
        "id": str(transfer.id),
        "center_name": transfer.center.name,
        "domain": transfer.center.domain,
        "status": transfer.status,
        "status_label": transfer.get_status_display(),
        "attempt_count": transfer.attempt_count,
        "last_error": transfer.last_error,
        "resident_id": transfer.resident_id,
        "next_attempt_at": transfer.next_attempt_at.isoformat()
        if transfer.status in ("pending", "retry")
        else None,
        "created_at": transfer.created_at.isoformat(),
        "attempts": [
            {
                "number": attempt.number,
                "outcome": attempt.outcome,
                "http_status": attempt.http_status,
                "started_at": attempt.started_at.isoformat(),
            }
            for attempt in transfer.attempts.order_by("-number")[:30]
        ],
    }


@endpoint(["GET", "POST"], authenticated=True)
def centers(request, organization_id):
    admin_membership(request.user, organization_id)
    if request.method == "POST":
        return JsonResponse(
            services.center_data(
                services.create_center(request.user, organization_id, request.payload),
                True,
            ),
            status=201,
        )
    return JsonResponse(
        {
            "items": [
                services.center_data(c, True)
                for c in RehubCenter.objects.filter(
                    organization_id=organization_id
                ).order_by("name")
            ]
        }
    )


@endpoint(["GET"], authenticated=True)
def destinations(request, organization_id):
    get_membership(request.user, organization_id)
    return JsonResponse(
        {
            "items": [
                services.center_data(c)
                for c in RehubCenter.objects.filter(
                    organization_id=organization_id,
                    is_active=True,
                    verified_at__isnull=False,
                ).order_by("name")
            ]
        }
    )


@endpoint(["POST"], authenticated=True)
def edit_center(request, organization_id, center_id):
    center = services.update_center(
        request.user, organization_id, center_id, request.payload
    )
    return JsonResponse(services.center_data(center, True))


@endpoint(["POST"], authenticated=True)
def verify_center(request, organization_id, center_id):
    center = services.verify_center(request.user, organization_id, center_id)
    return JsonResponse(services.center_data(center, True))


@endpoint(["GET", "POST"], authenticated=True)
def transfers(request, organization_id, lead_id):
    member = get_membership(request.user, organization_id)
    if request.method == "POST":
        transfer, created = services.queue_admission(
            request.user, organization_id, lead_id, request.payload
        )
        return JsonResponse(transfer_data(transfer), status=201 if created else 200)
    return JsonResponse(
        {
            "items": [
                transfer_data(t)
                for t in transfers_for(member, lead_id).prefetch_related("attempts")
            ]
        }
    )


@endpoint(["POST"], authenticated=True)
def retry(request, organization_id, transfer_id):
    transfer = services.retry_admission(request.user, organization_id, transfer_id)
    return JsonResponse(transfer_data(transfer))
