from django.contrib.auth import login
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone

from crm.accounts.serializers import session_data
from crm.core.http import endpoint
from crm.core.throttle import client_throttle, throttle
from crm.core.validation import clean_text

from . import branches, selectors, services
from .context import get_membership
from .permissions import Perm, can
from .serializers import (
    branch_data,
    event_data,
    invitation_data,
    member_data,
    organization_data,
)


@endpoint(["GET"], authenticated=True)
def organization(request, organization_id):
    return JsonResponse(
        organization_data(get_membership(request.user, organization_id))
    )


@endpoint(["GET"], authenticated=True)
def team(request, organization_id):
    viewer = get_membership(request.user, organization_id, Perm.MANAGE_TEAM)
    now = timezone.now()
    return JsonResponse(
        {
            "members": [
                member_data(m, viewer) for m in selectors.team_members(organization_id)
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


@endpoint(["POST"], authenticated=True)
def change_role(request, organization_id, membership_id):
    member = services.change_role(
        request.user, organization_id, membership_id, request.payload
    )
    return JsonResponse(member_data(member))


@endpoint(["POST"], authenticated=True)
def transfer_ownership(request, organization_id):
    throttle("ownership-user", str(request.user.pk), 10)
    services.transfer_ownership(request.user, organization_id, request.payload)
    return JsonResponse({"message": "Владение компанией передано."})


@endpoint(["GET", "POST"], authenticated=True)
def branch_list(request, organization_id):
    member = get_membership(request.user, organization_id)
    if request.method == "POST":
        branch = branches.create_branch(request.user, organization_id, request.payload)
        return JsonResponse(branch_data(branch), status=201)
    archived = can(member, Perm.MANAGE_BRANCHES) and request.GET.get("archived") == "1"
    return JsonResponse(
        {
            "items": [
                branch_data(b)
                for b in branches.company_branches(organization_id, archived)
            ]
        }
    )


@endpoint(["POST"], authenticated=True)
def edit_branch(request, organization_id, branch_id):
    branch = branches.rename_branch(
        request.user, organization_id, branch_id, request.payload
    )
    return JsonResponse(branch_data(branch))


@endpoint(["POST"], authenticated=True)
def archive_branch(request, organization_id, branch_id):
    branch = branches.set_branch_active(request.user, organization_id, branch_id, False)
    return JsonResponse(branch_data(branch))


@endpoint(["POST"], authenticated=True)
def restore_branch(request, organization_id, branch_id):
    branch = branches.set_branch_active(request.user, organization_id, branch_id, True)
    return JsonResponse(branch_data(branch))
