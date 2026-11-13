from django.utils import timezone

from . import audit
from .models import Membership
from .permissions import assignable_roles, granted, policy_for


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
        "branches": [
            branch_data(b) for b in org.branches.filter(is_active=True).order_by("name")
        ],
        "assignable_roles": assignable_roles(membership),
        "member_count": org.memberships.filter(is_active=True).count(),
        "created_at": org.created_at.isoformat(),
    }


def branch_data(branch):
    return {
        "id": str(branch.id),
        "name": branch.name,
        "is_active": branch.is_active,
        "version": branch.version,
    }


def member_data(m: Membership, viewer: Membership | None = None):
    manageable = bool(
        viewer
        and m.is_active
        and m.user_id != viewer.user_id
        and policy_for(viewer).manages(m.role)
    )
    return {
        "manageable": manageable,
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
