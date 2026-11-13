from django.http import JsonResponse

from crm.core.http import endpoint
from crm.core.throttle import throttle
from crm.organizations.context import get_membership

from . import tokens, tracking
from .http import extension_endpoint
from .selectors import lead_conversations, lead_search
from .serializers import conversation_data, token_data
from .services import import_fragment

# --- Кабинет CRM (сессия и CSRF) ---


@endpoint(["GET", "POST"], authenticated=True)
def extension_tokens(request, organization_id):
    member = get_membership(request.user, organization_id)
    if request.method == "POST":
        token, secret = tokens.issue_token(
            request.user, organization_id, request.payload
        )
        return JsonResponse(token_data(token, secret), status=201)
    return JsonResponse(
        {"items": [token_data(t) for t in tokens.visible_tokens(member)[:50]]}
    )


@endpoint(["POST"], authenticated=True)
def authorize_extension(request):
    throttle("extension-authorize", str(request.user.pk), 20)
    return JsonResponse(
        {"redirect": tokens.authorize_extension(request.user, request.payload)}
    )


@endpoint(["POST"], authenticated=True)
def revoke_extension_token(request, organization_id, token_id):
    token = tokens.revoke_token(request.user, organization_id, token_id)
    return JsonResponse(token_data(token))


@endpoint(["GET"], authenticated=True)
def conversations(request, organization_id, lead_id):
    member = get_membership(request.user, organization_id)
    return JsonResponse(
        {"items": [conversation_data(c) for c in lead_conversations(member, lead_id)]}
    )


# --- API расширения (только Bearer-ключ) ---


@extension_endpoint(["GET"])
def ext_session(request):
    context = request.extension
    return JsonResponse(
        {
            "company": context.member.organization.name,
            "user": context.member.user.name,
            "expires_at": context.token.expires_at.isoformat(),
        }
    )


@extension_endpoint(["GET"])
def ext_leads(request):
    query = request.GET.get("q", "").strip()[:160]
    return JsonResponse(
        {
            "items": [
                {
                    "id": str(lead.id),
                    "title": lead.title,
                    "client_name": lead.client.name,
                    "stage": lead.stage.name,
                }
                for lead in lead_search(request.extension.member, query)
            ]
        }
    )


@extension_endpoint(["POST"])
def ext_import(request):
    result, created = import_fragment(request.extension, request.payload)
    return JsonResponse(result, status=201 if created else 200)


@extension_endpoint(["GET"])
def ext_lookup(request):
    return JsonResponse(tracking.lookup(request.extension.member, request.GET))


@extension_endpoint(["POST"])
def ext_track(request):
    return JsonResponse(tracking.track(request.extension, request.payload))


@extension_endpoint(["POST"])
def ext_untrack(request):
    return JsonResponse(tracking.untrack(request.extension, request.payload))


@extension_endpoint(["GET"])
def ext_match(request):
    leads = tracking.match_leads(request.extension.member, request.GET.get("phone"))
    return JsonResponse(
        {
            "items": [
                {
                    "id": str(lead.id),
                    "title": lead.title,
                    "client_name": lead.client.name,
                    "stage": lead.stage.name,
                }
                for lead in leads
            ]
        }
    )
