from .models import AuditEvent, Invitation, Membership


def team_members(organization_id):
    return (
        Membership.objects.filter(organization_id=organization_id)
        .select_related("user")
        .order_by("created_at")
    )


def recent_invitations(organization_id, limit=100):
    return Invitation.objects.filter(organization_id=organization_id).order_by(
        "-created_at"
    )[:limit]


def recent_events(organization_id, limit=50):
    return (
        AuditEvent.objects.filter(organization_id=organization_id)
        .select_related("actor")
        .order_by("-created_at")[:limit]
    )


def active_memberships(user):
    return (
        user.memberships.filter(is_active=True)
        .select_related("organization")
        .order_by("organization__name", "organization_id")
    )
