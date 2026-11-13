"""Бизнес-операции продаж. Не зависят от HTTP и интерфейса."""

from django.db import transaction

from crm.core.errors import ApiError
from crm.core.phones import phone_digits
from crm.core.validation import clean_text, identifier, optional, require_version
from crm.organizations import audit
from crm.organizations.context import get_membership
from crm.organizations.models import Branch, Membership
from crm.organizations.permissions import Perm, can

from .lead_changes import ChangeContext, apply_changes
from .models import Client, Lead, LeadActivity, LeadStageChange, RelatedContact
from .pipeline import initial_stage
from .selectors import find_client, find_lead
from .validation import client_fields


@transaction.atomic
def create_client(actor, company_id, data):
    get_membership(actor, company_id)
    client = Client.objects.create(
        organization_id=company_id, created_by=actor, **client_fields(data)
    )
    audit.record(company_id, actor, "client.created", client.id)
    return client


@transaction.atomic
def update_client(actor, company_id, client_id, data):
    member = get_membership(actor, company_id)
    client = find_client(member, client_id, lock=True)
    require_version(client, data, "Карточка изменилась. Откройте её заново.")
    for key, value in client_fields(data).items():
        setattr(client, key, value)
    client.version += 1
    client.save()
    audit.record(company_id, actor, "client.updated", client.id)
    return client


def _touch_client(client):
    """Контакты входят в снимок передачи: их изменение меняет версию карточки,
    и подтверждение по устаревшему предпросмотру отклоняется."""
    client.version += 1
    client.save(update_fields=["version", "updated_at"])


@transaction.atomic
def create_contact(actor, company_id, client_id, data):
    member = get_membership(actor, company_id)
    client = find_client(member, client_id, lock=True)
    contact = RelatedContact.objects.create(client=client, **_contact_fields(data))
    _touch_client(client)
    return contact


def _contact_fields(data):
    phone = optional(data, "phone", 40)
    return dict(
        name=clean_text(data.get("name"), "Имя контакта", 240),
        relationship=clean_text(data.get("relationship"), "Кем приходится", 80),
        phone=phone,
        phone_digits=phone_digits(phone),
    )


def _find_contact(member, client_id, contact_id):
    # Контакт наследует границу доступа карточки клиента.
    client = find_client(member, client_id, lock=True)
    contact = (
        RelatedContact.objects.select_for_update()
        .filter(pk=identifier(contact_id), client=client)
        .first()
    )
    if not contact:
        raise ApiError("Контактное лицо не найдено.", 404)
    return contact


@transaction.atomic
def update_contact(actor, company_id, client_id, contact_id, data):
    member = get_membership(actor, company_id)
    contact = _find_contact(member, client_id, contact_id)
    require_version(contact, data, "Контакт изменился. Откройте карточку заново.")
    for key, value in _contact_fields(data).items():
        setattr(contact, key, value)
    contact.version += 1
    contact.save()
    _touch_client(contact.client)
    audit.record(company_id, actor, "contact.updated", contact.id)
    return contact


@transaction.atomic
def delete_contact(actor, company_id, client_id, contact_id):
    member = get_membership(actor, company_id)
    contact = _find_contact(member, client_id, contact_id)
    audit.record(company_id, actor, "contact.deleted", contact.id)
    client = contact.client
    contact.delete()
    _touch_client(client)


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
    if not branch.is_active:
        raise ApiError("Филиал в архиве. Выберите действующий филиал.")
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
    LeadStageChange.objects.create(lead=lead, to_stage=lead.stage, actor=actor)
    return lead


@transaction.atomic
def update_lead(actor, company_id, lead_id, data):
    # Компания блокируется только при смене ответственного (сериализация с
    # отключением сотрудников); перенос на доске блокирует лишь своё обращение.
    member = get_membership(actor, company_id, lock="assignee_id" in data)
    lead = find_lead(member, lead_id, lock=True)
    require_version(lead, data, "Обращение изменилось. Откройте его заново.")
    previous_stage_id = lead.stage_id
    changes = apply_changes(
        lead, data, ChangeContext(member, company_id, company_assignee)
    )
    lead.version += 1
    lead.save()
    if lead.stage_id != previous_stage_id:
        LeadStageChange.objects.create(
            lead=lead,
            from_stage_id=previous_stage_id,
            to_stage_id=lead.stage_id,
            actor=actor,
        )
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
