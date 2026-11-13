"""Бизнес-операции продаж. Не зависят от HTTP и интерфейса."""

from django.db import transaction

from crm.core.errors import ApiError
from crm.core.validation import clean_text, identifier, optional
from crm.organizations.context import get_membership
from crm.organizations.models import Branch, Membership
from crm.organizations.permissions import Perm, can

from .lead_changes import ChangeContext, apply_changes
from .models import Client, Lead, LeadActivity, RelatedContact
from .pipeline import initial_stage
from .selectors import find_client, find_lead
from .validation import client_fields


def require_version(obj, data, message):
    if data.get("version") != obj.version:
        raise ApiError(message, 409)


def create_client(actor, company_id, data):
    get_membership(actor, company_id)
    return Client.objects.create(
        organization_id=company_id, created_by=actor, **client_fields(data)
    )


@transaction.atomic
def update_client(actor, company_id, client_id, data):
    member = get_membership(actor, company_id)
    client = find_client(member, client_id, lock=True)
    require_version(client, data, "Карточка изменилась. Откройте её заново.")
    for key, value in client_fields(data).items():
        setattr(client, key, value)
    client.version += 1
    client.save()
    return client


def create_contact(actor, company_id, client_id, data):
    member = get_membership(actor, company_id)
    client = find_client(member, client_id)
    return RelatedContact.objects.create(
        client=client,
        name=clean_text(data.get("name"), "Имя контакта", 240),
        relationship=clean_text(data.get("relationship"), "Кем приходится", 80),
        phone=optional(data, "phone", 40),
    )


def company_assignee(company_id, value):
    assignee = (
        Membership.objects.filter(
            pk=identifier(value), organization_id=company_id, is_active=True
        )
        .select_related("user")
        .first()
    )
    if not assignee:
        raise ApiError("Ответственный недоступен в этой компании.")
    return assignee


def company_branch(company_id, value):
    branch = Branch.objects.filter(
        pk=identifier(value), organization_id=company_id
    ).first()
    if not branch:
        raise ApiError("Филиал должен принадлежать этой компании.")
    return branch


@transaction.atomic
def create_lead(actor, company_id, data):
    # Блокировка компании сериализует назначение с отключением сотрудников.
    member = get_membership(actor, company_id, lock=True)
    client = find_client(member, identifier(data.get("client_id")))
    assignee_id = data.get("assignee_id", str(member.id))
    if not can(member, Perm.ASSIGN_LEADS) and str(assignee_id) != str(member.id):
        raise ApiError("Менеджер может назначить обращение только себе.", 403)
    lead = Lead.objects.create(
        organization_id=company_id,
        client=client,
        assignee=company_assignee(company_id, assignee_id),
        branch=company_branch(company_id, data.get("branch_id")),
        stage=initial_stage(company_id),
        title=clean_text(data.get("title"), "Название обращения", 240),
        source=optional(data, "source", 120),
    )
    LeadActivity.objects.create(
        lead=lead, actor=actor, kind="created", text="Обращение создано"
    )
    return lead


@transaction.atomic
def update_lead(actor, company_id, lead_id, data):
    member = get_membership(actor, company_id, lock=True)
    lead = find_lead(member, lead_id, lock=True)
    require_version(lead, data, "Обращение изменилось. Откройте его заново.")
    changes = apply_changes(
        lead, data, ChangeContext(member, company_id, company_assignee)
    )
    lead.version += 1
    lead.save()
    if changes:
        LeadActivity.objects.create(
            lead=lead, actor=actor, kind="changed", text="; ".join(changes)
        )
    return lead


def add_comment(actor, company_id, lead_id, data):
    member = get_membership(actor, company_id)
    lead = find_lead(member, lead_id)
    return LeadActivity.objects.create(
        lead=lead,
        actor=actor,
        kind="comment",
        text=clean_text(data.get("text"), "Комментарий", 5000),
    )
