"""Операции платформы: только суперпользователь создаёт компании.

Глобальная роль не даёт доступа к данным компаний: суперпользователь видит
сведения о компании только как её участник."""

from django.db import transaction

from crm.core.errors import ApiError
from crm.core.validation import clean_email, clean_text
from crm.organizations.models import Organization
from crm.organizations.services import create_organization, invite_owner
from crm.sales.pipeline import create_default_stages


def require_platform_admin(user):
    if not (user.is_authenticated and user.is_active and user.is_superuser):
        raise ApiError("Создавать компании может только администратор платформы.", 403)


@transaction.atomic
def create_company(actor, data):
    """Без почты владельца владельцем становится сам администратор платформы."""
    require_platform_admin(actor)
    name = clean_text(data.get("name"), "Название компании", 160)
    raw_email = data.get("owner_email") or ""
    owner_email = clean_email(raw_email) if raw_email.strip() else actor.email
    self_owned = owner_email.lower() == actor.email.lower()
    organization = create_organization(actor, name, actor if self_owned else None)
    create_default_stages(organization)
    if not self_owned:
        invite_owner(actor, organization, owner_email)
    return organization


@transaction.atomic
def reinvite_owner(actor, organization_id, data):
    require_platform_admin(actor)
    organization = (
        Organization.objects.select_for_update().filter(pk=organization_id).first()
    )
    if not organization:
        raise ApiError("Компания не найдена.", 404)
    return invite_owner(actor, organization, clean_email(data.get("owner_email")))
