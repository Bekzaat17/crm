from django.http import JsonResponse

from crm.core.http import endpoint

from . import selectors, services


def company_data(organization):
    return {
        "id": str(organization.id),
        "name": organization.name,
        "created_at": organization.created_at.isoformat(),
        "members": getattr(organization, "members", None),
        "owner": selectors.owner_status(organization),
    }


@endpoint(["GET", "POST"], authenticated=True)
def companies(request):
    services.require_platform_admin(request.user)
    if request.method == "POST":
        organization = services.create_company(request.user, request.payload)
        return JsonResponse(company_data(organization), status=201)
    return JsonResponse(
        {"items": [company_data(o) for o in selectors.companies()[:200]]}
    )


@endpoint(["POST"], authenticated=True)
def reinvite_owner(request, organization_id):
    services.reinvite_owner(request.user, organization_id, request.payload)
    return JsonResponse({"message": "Приглашение владельцу отправлено."})
