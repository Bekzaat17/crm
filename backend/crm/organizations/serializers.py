from django.utils import timezone

from . import audit
from .models import Membership
from .permissions import Perm, can, granted


def company_data(membership):
    return {
        "id": str(membership.organization_id),
        "name": membership.organization.name,
        "role": membership.role,
        "role_label": membership.get_role_display(),
    }


def organization_data(membership):
    org = membership.organization
    return {
        **company_data(membership),
        "permissions": granted(membership),
        "can_manage_team": can(membership, Perm.MANAGE_TEAM),
        "branches": [
            {"id": str(b.id), "name": b.name} for b in org.branches.order_by("name")
        ],
        "member_count": org.memberships.filter(is_active=True).count(),
        "created_at": org.created_at.isoformat(),
    }


def member_data(m: Membership):
    return {
        "id": str(m.id),
        "user_id": str(m.user_id),
        "name": m.user.name,
        "email": m.user.email,
        "role": m.role,
        "role_label": m.get_role_display(),
        "is_active": m.is_active,
    }


def invitation_status(invitation, now):
    if invitation.accepted_at:
        return "accepted"
    if invitation.revoked_at:
        return "revoked"
    return "expired" if invitation.expires_at <= now else "pending"


def invitation_data(invitation, now=None):
    return {
        "id": str(invitation.id),
        "email": invitation.email,
        "role": invitation.role,
        "role_label": invitation.get_role_display(),
        "created_at": invitation.created_at.isoformat(),
        "expires_at": invitation.expires_at.isoformat(),
        "status": invitation_status(invitation, now or timezone.now()),
    }


def event_data(event):
    return {
        "id": str(event.id),
        "action": audit.label(event.action),
        "actor": event.actor.name,
        "created_at": event.created_at.isoformat(),
    }
