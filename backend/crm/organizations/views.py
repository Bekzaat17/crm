from django.contrib.auth import login
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone

from crm.accounts.serializers import session_data
from crm.core.http import endpoint
from crm.core.throttle import client_throttle, throttle
from crm.core.validation import clean_text

from . import selectors, services
from .context import get_membership
from .permissions import Perm
from .serializers import event_data, invitation_data, member_data, organization_data


@endpoint(["GET"], authenticated=True)
def organization(request, organization_id):
    return JsonResponse(
        organization_data(get_membership(request.user, organization_id))
    )


@endpoint(["GET"], authenticated=True)
def team(request, organization_id):
    get_membership(request.user, organization_id, Perm.MANAGE_TEAM)
    now = timezone.now()
    return JsonResponse(
        {
            "members": [
                member_data(m) for m in selectors.team_members(organization_id)
            ],
            "invitations": [
                invitation_data(i, now)
                for i in selectors.recent_invitations(organization_id)
            ],
        }
    )


@endpoint(["POST"], authenticated=True)
def create_invitation(request, organization_id):
    # Проверяем компанию до ограничения частоты, чтобы чужие UUID не расходовали квоту.
    get_membership(request.user, organization_id, Perm.MANAGE_TEAM)
    throttle("invite-company", str(organization_id), 30)
    invitation = services.invite_member(request.user, organization_id, request.payload)
    return JsonResponse(
        {
            "id": str(invitation.id),
            "message": "Приглашение отправлено на почту сотрудника.",
        },
        status=201,
    )


@endpoint(["POST"])
def invitation_preview(request):
    client_throttle(request, "invite-preview", 60)
    token = clean_text(request.payload.get("token"), "Приглашение", 256)
    invitation = services.available_invitation(token)
    return JsonResponse(
        {
            "company_name": invitation.organization.name,
            "email": invitation.email,
            "role_label": invitation.get_role_display(),
            "expires_at": invitation.expires_at.isoformat(),
        }
    )


@endpoint(["POST"])
def accept_invitation(request):
    client_throttle(request, "invite-accept", 20)
    token = clean_text(request.payload.get("token"), "Приглашение", 256)
    user, organization_id = services.accept_invitation(
        token, request.user, request.payload
    )
    login(request, user)
    return JsonResponse(
        {
            **session_data(user),
            "organization_id": str(organization_id),
            "csrf_token": get_token(request),
        }
    )


@endpoint(["POST"], authenticated=True)
def revoke_invitation(request, organization_id, invitation_id):
    services.revoke_invitation(request.user, organization_id, invitation_id)
    return JsonResponse({"message": "Приглашение отозвано."})


@endpoint(["POST"], authenticated=True)
def deactivate_member(request, organization_id, membership_id):
    services.deactivate_member(request.user, organization_id, membership_id)
    return JsonResponse({"message": "Доступ сотрудника отключён."})


@endpoint(["GET"], authenticated=True)
def audit(request, organization_id):
    get_membership(request.user, organization_id, Perm.VIEW_AUDIT)
    return JsonResponse(
        {"events": [event_data(e) for e in selectors.recent_events(organization_id)]}
    )
