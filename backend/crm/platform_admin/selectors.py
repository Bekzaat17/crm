from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from crm.organizations.models import Invitation, Membership, Organization


def companies():
    owners = Membership.objects.filter(
        role=Membership.Role.OWNER, is_active=True
    ).select_related("user")
    invitations = Invitation.objects.filter(
        role=Membership.Role.OWNER, accepted_at__isnull=True, revoked_at__isnull=True
    ).order_by("-created_at")
    return (
        Organization.objects.annotate(
            members=Count("memberships", filter=Q(memberships__is_active=True))
        )
        .prefetch_related(
            Prefetch("memberships", queryset=owners, to_attr="owners"),
            Prefetch("invitations", queryset=invitations, to_attr="owner_invites"),
        )
        .order_by("-created_at")
    )


def owner_status(organization):
    """Ожидает предзагрузки из companies(); для одной компании подгружает сама."""
    if not hasattr(organization, "owners"):
        organization = companies().get(pk=organization.pk)
    if organization.owners:
        owner = organization.owners[0]
        return {"state": "active", "email": owner.user.email, "name": owner.user.name}
    if organization.owner_invites:
        invite = organization.owner_invites[0]
        return {
            "state": "invited" if invite.expires_at > timezone.now() else "expired",
            "email": invite.email,
            "expires_at": invite.expires_at.isoformat(),
        }
    return {"state": "missing"}
