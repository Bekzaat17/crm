from django.db.models import Count, Q

from crm.organizations.models import Invitation, Membership, Organization


def companies():
    return Organization.objects.annotate(
        members=Count("memberships", filter=Q(memberships__is_active=True))
    ).order_by("-created_at")


def owner_status(organization):
    owner = (
        Membership.objects.filter(
            organization=organization, role=Membership.Role.OWNER, is_active=True
        )
        .select_related("user")
        .first()
    )
    if owner:
        return {"state": "active", "email": owner.user.email, "name": owner.user.name}
    pending = (
        Invitation.objects.filter(
            organization=organization,
            role=Membership.Role.OWNER,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if pending:
        return {
            "state": "invited",
            "email": pending.email,
            "expires_at": pending.expires_at.isoformat(),
        }
    return {"state": "missing"}
