"""Компания, приглашения и состав команды. Не зависят от HTTP."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from crm.accounts.models import User
from crm.accounts.passwords import check_password
from crm.core.errors import ApiError
from crm.core.mail import Mailer, default_mailer
from crm.core.tokens import digest, new_token
from crm.core.validation import clean_email, clean_text

from . import audit
from .context import get_membership
from .emails import invitation_email
from .models import Branch, Invitation, Membership, Organization
from .permissions import Perm

INVITABLE_ROLES = (
    Membership.Role.ADMIN,
    Membership.Role.LEAD,
    Membership.Role.MANAGER,
)


def create_organization(owner, name):
    """Компания создаётся только вместе с владельцем и основным филиалом."""
    organization = Organization.objects.create(name=name)
    Membership.objects.create(
        user=owner, organization=organization, role=Membership.Role.OWNER
    )
    Branch.objects.create(organization=organization, name="Основной центр")
    audit.record(organization.id, owner, "organization.created", organization.id)
    return organization


@transaction.atomic
def invite_member(actor, organization_id, data, mailer: Mailer | None = None):
    # Блокировка компании сериализует приглашения и изменения состава.
    membership = get_membership(actor, organization_id, Perm.MANAGE_TEAM, lock=True)
    organization = membership.organization
    email = clean_email(data.get("email"))
    role = data.get("role")
    if role not in INVITABLE_ROLES:
        raise ApiError("Выберите роль администратора, руководителя или менеджера.")
    if Membership.objects.filter(
        organization=organization, user__email__iexact=email, is_active=True
    ).exists():
        raise ApiError("Этот сотрудник уже состоит в компании.", 409)
    now = timezone.now()
    existing = Invitation.objects.filter(
        organization=organization,
        email=email,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    )
    if existing.filter(expires_at__gt=now).exists():
        raise ApiError(
            "Приглашение уже отправлено. Сначала отзовите его для повторной отправки.",
            409,
        )
    existing.update(revoked_at=now)
    token = new_token()
    invitation = Invitation.objects.create(
        organization=organization,
        email=email,
        role=role,
        invited_by=actor,
        token_hash=digest(token),
        expires_at=now + timedelta(days=7),
    )
    audit.record(organization.id, actor, "invitation.created", invitation.id)
    # Письмо отправляется до commit: ошибка SMTP не оставляет активное приглашение.
    (mailer or default_mailer()).send(invitation_email(invitation, token))
    return invitation


def available_invitation(token, lock=False):
    queryset = Invitation.objects.select_related("organization")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    invitation = queryset.filter(
        token_hash=digest(token),
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if not invitation:
        raise ApiError(
            "Приглашение недействительно, отозвано или уже использовано.", 404
        )
    return invitation


def _invited_user(invitation, current_user, data):
    if current_user.is_authenticated:
        if current_user.email.lower() != invitation.email:
            raise ApiError("Войдите с почтой, на которую отправлено приглашение.", 403)
        return current_user
    if User.objects.filter(email__iexact=invitation.email).exists():
        raise ApiError("Аккаунт с этой почтой уже есть. Сначала войдите в него.", 409)
    name = clean_text(data.get("name"), "Ваше имя", 120)
    password = check_password(data.get("password"), invitation.email, name)
    return User.objects.create_user(
        email=invitation.email, password=password, name=name
    )


@transaction.atomic
def accept_invitation(token, current_user, data):
    invitation = available_invitation(token, lock=True)
    user = _invited_user(invitation, current_user, data)
    membership, created = Membership.objects.get_or_create(
        organization=invitation.organization,
        user=user,
        defaults={"role": invitation.role},
    )
    if not created and not membership.is_active:
        membership.role, membership.is_active = invitation.role, True
        membership.save(update_fields=["role", "is_active"])
    # Существующему активному сотруднику приглашение не меняет роль.
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    audit.record(invitation.organization_id, user, "invitation.accepted", invitation.id)
    return user, invitation.organization_id


@transaction.atomic
def revoke_invitation(actor, organization_id, invitation_id):
    get_membership(actor, organization_id, Perm.MANAGE_TEAM)
    invitation = (
        Invitation.objects.select_for_update()
        .filter(pk=invitation_id, organization_id=organization_id)
        .first()
    )
    if not invitation:
        raise ApiError("Приглашение не найдено.", 404)
    if invitation.accepted_at or invitation.revoked_at:
        raise ApiError("Приглашение уже закрыто.", 409)
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["revoked_at"])
    audit.record(organization_id, actor, "invitation.revoked", invitation.id)


@transaction.atomic
def deactivate_member(actor, organization_id, membership_id):
    get_membership(actor, organization_id, Perm.MANAGE_TEAM, lock=True)
    target = (
        Membership.objects.select_for_update()
        .filter(pk=membership_id, organization_id=organization_id)
        .first()
    )
    if not target:
        raise ApiError("Сотрудник не найден.", 404)
    if target.role == Membership.Role.OWNER or target.user_id == actor.pk:
        raise ApiError(
            "Владельца и собственный доступ нельзя отключить через управление командой.",
            403,
        )
    target.is_active = False
    target.save(update_fields=["is_active"])
    audit.record(organization_id, actor, "membership.deactivated", target.id)
