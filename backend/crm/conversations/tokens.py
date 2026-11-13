"""Токены расширения: хранится только хеш, открытый токен показывается один раз."""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from crm.core.errors import ApiError
from crm.core.tokens import digest, new_token
from crm.core.validation import clean_text, identifier
from crm.organizations import audit
from crm.organizations.context import get_membership
from crm.organizations.models import Membership
from crm.organizations.permissions import Perm, can

from .models import ExtensionToken

PREFIX = "crx_"
TTL = timedelta(days=90)
MAX_ACTIVE = 10


@dataclass(frozen=True)
class ExtensionContext:
    token: ExtensionToken
    member: Membership


def visible_tokens(member):
    tokens = ExtensionToken.objects.filter(organization_id=member.organization_id)
    if not can(member, Perm.MANAGE_TEAM):
        tokens = tokens.filter(user=member.user)
    return tokens.select_related("user").order_by("-created_at")


@transaction.atomic
def issue_token(actor, company_id, data):
    member = get_membership(actor, company_id)
    active = ExtensionToken.objects.filter(
        organization_id=company_id,
        user=actor,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    )
    if active.count() >= MAX_ACTIVE:
        raise ApiError("Отзовите неиспользуемые ключи расширения.", 409)
    secret = PREFIX + new_token()
    token = ExtensionToken.objects.create(
        organization_id=company_id,
        user=member.user,
        name=clean_text(data.get("name", "Браузер"), "Название", 80),
        token_hash=digest(secret),
        expires_at=timezone.now() + TTL,
    )
    audit.record(company_id, actor, "extension_token.created", token.id)
    return token, secret


@transaction.atomic
def revoke_token(actor, company_id, token_id):
    member = get_membership(actor, company_id)
    token = (
        visible_tokens(member)
        .select_for_update(of=("self",))
        .filter(pk=identifier(token_id))
        .first()
    )
    if not token:
        raise ApiError("Ключ не найден.", 404)
    if token.revoked_at is None:
        token.revoked_at = timezone.now()
        token.save(update_fields=["revoked_at"])
        audit.record(company_id, actor, "extension_token.revoked", token.id)
    return token


def authenticate(header):
    """Bearer-токен → контекст. Отключённый сотрудник теряет доступ сразу."""
    scheme, _, secret = (header or "").partition(" ")
    if scheme != "Bearer" or not secret.startswith(PREFIX) or len(secret) > 100:
        raise ApiError("Нужен ключ расширения.", 401)
    token = (
        ExtensionToken.objects.select_related("user")
        .filter(
            token_hash=digest(secret),
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    member = (
        Membership.objects.select_related("organization", "user")
        .filter(
            user_id=token.user_id,
            organization_id=token.organization_id,
            is_active=True,
            user__is_active=True,
        )
        .first()
        if token
        else None
    )
    if not member:
        raise ApiError("Ключ расширения недействителен или отозван.", 401)
    ExtensionToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
    return ExtensionContext(token, member)
