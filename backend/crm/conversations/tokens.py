"""Токены расширения: хранится только хеш, открытый токен показывается один раз."""

import re
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
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


def revoke_user_tokens(user, organization_id=None):
    """Отзыв ключей при отключении сотрудника или смене пароля: повторное
    подключение или захват аккаунта не должны оживлять старые ключи."""
    tokens = ExtensionToken.objects.filter(user=user, revoked_at__isnull=True)
    if organization_id is not None:
        tokens = tokens.filter(organization_id=organization_id)
    return tokens.update(revoked_at=timezone.now())


@transaction.atomic
def issue_token(actor, company_id, data):
    # Блокировка компании: параллельные входы не превысят лимит ключей.
    member = get_membership(actor, company_id, lock=True)
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


REDIRECT = re.compile(r"^https://([a-p]{32})\.chromiumapp\.org/[A-Za-z0-9_/-]{0,100}$")
STATE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def authorize_extension(actor, data):
    """Вход расширения через CRM (chrome.identity.launchWebAuthFlow).

    Ключ передаётся только на адрес расширения из CRM_EXTENSION_IDS в
    фрагменте URL; браузер не отправляет фрагмент на сервер."""
    redirect_uri = data.get("redirect_uri")
    match = REDIRECT.match(redirect_uri) if isinstance(redirect_uri, str) else None
    if not match or match.group(1) not in settings.EXTENSION_IDS:
        raise ApiError("Это расширение не разрешено для подключения к CRM.", 403)
    state = data.get("state")
    if not isinstance(state, str) or not STATE.match(state):
        raise ApiError("Некорректный запрос подключения расширения.")
    company_id = identifier(data.get("company_id"))
    token, secret = issue_token(actor, company_id, {"name": "Расширение браузера"})
    fragment = urlencode(
        {
            "token": secret,
            "state": state,
            "company": token.organization.name,
        }
    )
    return f"{redirect_uri}#{fragment}"


def revoke_current(token):
    ExtensionToken.objects.filter(pk=token.pk, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
