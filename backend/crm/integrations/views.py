from django.http import JsonResponse

from crm.core.http import endpoint
from crm.organizations.context import get_membership
from crm.organizations.permissions import Perm

from . import selectors, services
from .serializers import center_data, transfer_data


@endpoint(["GET", "POST"], authenticated=True)
def centers(request, organization_id):
    get_membership(request.user, organization_id, Perm.MANAGE_CENTERS)
    if request.method == "POST":
        center = services.create_center(request.user, organization_id, request.payload)
        return JsonResponse(center_data(center, True), status=201)
    return JsonResponse(
        {
            "items": [
                center_data(c, True) for c in selectors.company_centers(organization_id)
            ]
        }
    )


@endpoint(["GET"], authenticated=True)
def destinations(request, organization_id):
    get_membership(request.user, organization_id)
    return JsonResponse(
        {"items": [center_data(c) for c in selectors.destinations(organization_id)]}
    )


@endpoint(["POST"], authenticated=True)
def edit_center(request, organization_id, center_id):
    center = services.update_center(
        request.user, organization_id, center_id, request.payload
    )
    return JsonResponse(center_data(center, True))


@endpoint(["POST"], authenticated=True)
def verify_center(request, organization_id, center_id):
    center = services.verify_center(request.user, organization_id, center_id)
    return JsonResponse(center_data(center, True))


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
                for t in selectors.transfers_for(member, lead_id).prefetch_related(
                    "attempts"
                )
            ]
        }
    )


@endpoint(["POST"], authenticated=True)
def retry(request, organization_id, transfer_id):
    transfer = services.retry_admission(request.user, organization_id, transfer_id)
    return JsonResponse(transfer_data(transfer))
