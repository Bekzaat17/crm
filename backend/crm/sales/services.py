"""Бизнес-операции продаж. Не зависят от HTTP и интерфейса."""

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from crm.models import (
    Branch,
    Client,
    Lead,
    LeadActivity,
    Membership,
    Organization,
    RelatedContact,
)
from crm.services import ApiError, clean_text, get_membership

from .selectors import find_client, find_lead
from .validation import client_fields, identifier, optional


def create_client(actor, company_id, data):
    get_membership(actor, company_id)
    return Client.objects.create(
        organization_id=company_id, created_by=actor, **client_fields(data)
    )


@transaction.atomic
def update_client(actor, company_id, client_id, data):
    member = get_membership(actor, company_id)
    client = find_client(member, client_id, lock=True)
    if data.get("version") != client.version:
        raise ApiError("Карточка изменилась. Откройте её заново.", 409)
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


@transaction.atomic
def create_lead(actor, company_id, data):
    get_membership(actor, company_id)
    Organization.objects.select_for_update().get(pk=company_id)
    member = get_membership(actor, company_id)
    client = find_client(member, identifier(data.get("client_id")))
    assignee_id = data.get("assignee_id", str(member.id))
    if member.role == "manager" and str(assignee_id) != str(member.id):
        raise ApiError("Менеджер может назначить обращение только себе.", 403)
    assignee = company_assignee(company_id, assignee_id)
    branch = Branch.objects.filter(
        pk=identifier(data.get("branch_id")), organization_id=company_id
    ).first()
    if not branch:
        raise ApiError("Филиал должен принадлежать этой компании.")
    lead = Lead.objects.create(
        organization_id=company_id,
        client=client,
        assignee=assignee,
        branch=branch,
        title=clean_text(data.get("title"), "Название обращения", 240),
        source=optional(data, "source", 120),
    )
    LeadActivity.objects.create(
        lead=lead, actor=actor, kind="created", text="Обращение создано"
    )
    return lead


@transaction.atomic
def update_lead(actor, company_id, lead_id, data):
    get_membership(actor, company_id)
    Organization.objects.select_for_update().get(pk=company_id)
    member = get_membership(actor, company_id)
    lead = find_lead(member, lead_id, lock=True)
    if data.get("version") != lead.version:
        raise ApiError("Обращение изменилось. Откройте его заново.", 409)
    changes = []
    stage = data.get("stage", lead.stage)
    if stage not in Lead.Stage.values:
        raise ApiError("Неизвестный этап.")
    reason = (
        optional(data, "refusal_reason", 500)
        if "refusal_reason" in data
        else lead.refusal_reason
    )
    if stage == "refused" and not reason:
        raise ApiError("Укажите причину отказа.")
    if stage != lead.stage:
        changes.append(f"Этап: {lead.get_stage_display()} → {Lead.Stage(stage).label}")
    if stage == "refused" and reason != lead.refusal_reason:
        changes.append(f"Причина отказа: {reason}")
    lead.stage = stage
    lead.refusal_reason = reason if stage == "refused" else ""
    if "assignee_id" in data and str(data["assignee_id"]) != str(lead.assignee_id):
        if member.role == "manager":
            raise ApiError("Менеджер не может переназначать обращения.", 403)
        lead.assignee = company_assignee(company_id, data["assignee_id"])
        changes.append(f"Ответственный: {lead.assignee.user.name}")
    if "next_contact_at" in data:
        raw = data["next_contact_at"]
        try:
            dt = parse_datetime(raw) if isinstance(raw, str) and raw else None
        except ValueError:
            dt = None
        if raw is not None and raw != "" and (not dt or timezone.is_naive(dt)):
            raise ApiError("Укажите дату и время с часовым поясом.")
        if lead.next_contact_at != dt:
            lead.next_contact_at = dt
            changes.append("Обновлено время следующего контакта")
    if "title" in data:
        title = clean_text(data["title"], "Название обращения", 240)
        if title != lead.title:
            lead.title = title
            changes.append("Обновлено название обращения")
    if "source" in data:
        source = optional(data, "source", 120)
        if source != lead.source:
            lead.source = source
            changes.append("Обновлён источник")
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
