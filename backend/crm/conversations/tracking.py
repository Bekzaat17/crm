"""Отслеживание чатов: сотрудник один раз включает галочку, дальше расширение
само передаёт новые сообщения этого чата в выбранное обращение."""

from django.db import transaction
from django.db.models import Q

from crm.core.errors import ApiError
from crm.core.phones import phone_digits
from crm.core.validation import clean_text, identifier
from crm.sales.models import LeadActivity, PipelineStage
from crm.sales.selectors import clients_for, find_lead, leads_for

from .models import Conversation, Source
from .validation import clean_external_id, clean_source


def _visible(member, source, external_id):
    """Диалог компании, если его обращение доступно сотруднику."""
    conversation = (
        Conversation.objects.select_related("lead__client")
        .filter(
            organization_id=member.organization_id,
            source=source,
            external_id=external_id,
        )
        .first()
    )
    if conversation and leads_for(member).filter(pk=conversation.lead_id).exists():
        return conversation
    return None


def summary(conversation):
    if conversation is None:
        return {"tracked": False}
    return {
        "tracked": conversation.tracking,
        "conversation_id": str(conversation.id),
        "lead": {
            "id": str(conversation.lead_id),
            "title": conversation.lead.title,
            "client_name": conversation.lead.client.name,
        },
        "message_count": conversation.messages.count(),
    }


def lookup(member, query):
    return summary(
        _visible(
            member,
            clean_source(query.get("source")),
            clean_external_id(query.get("external_id")),
        )
    )


@transaction.atomic
def track(context, data):
    member = context.member
    source, external_id = (
        clean_source(data.get("source")),
        clean_external_id(data.get("external_id")),
    )
    lead = find_lead(member, identifier(data.get("lead_id")), lock=True)
    title = clean_text(data.get("title"), "Название диалога", 200)
    conversation, created = Conversation.objects.select_for_update().get_or_create(
        organization_id=member.organization_id,
        source=source,
        external_id=external_id,
        defaults=dict(lead=lead, title=title, created_by=member.user),
    )
    if not created and conversation.lead_id != lead.id:
        # Чат привязан к обращению, которое сотрудник не видит: не трогаем.
        visible = leads_for(member).filter(pk=conversation.lead_id).exists()
        if not visible or conversation.messages.exists():
            raise ApiError(
                "Этот чат уже привязан к другому обращению. Измените привязку в CRM.",
                409,
            )
        conversation.lead = lead
    conversation.title = title
    conversation.tracking = True
    conversation.save()
    LeadActivity.objects.create(
        lead=lead,
        actor=member.user,
        kind="import",
        text=f"Включено отслеживание чата {Source(source).label}",
    )
    return summary(conversation)


@transaction.atomic
def untrack(context, data):
    member = context.member
    conversation = _visible(
        member,
        clean_source(data.get("source")),
        clean_external_id(data.get("external_id")),
    )
    if conversation is None:
        raise ApiError("Чат не отслеживается.", 404)
    conversation.tracking = False
    conversation.save(update_fields=["tracking", "updated_at"])
    LeadActivity.objects.create(
        lead=conversation.lead,
        actor=member.user,
        kind="import",
        text=f"Выключено отслеживание чата {conversation.get_source_display()}",
    )
    return summary(conversation)


def match_leads(member, raw_phone, limit=10):
    """Обращения клиентов с этим номером. Номер не уникален: семьи делят телефон,
    поэтому возвращается список, выбор подтверждает сотрудник."""
    digits = phone_digits(raw_phone)
    if len(digits) < 6:
        return []
    clients = clients_for(member).filter(
        Q(phone_digits=digits) | Q(contacts__phone_digits=digits)
    )
    leads = (
        leads_for(member)
        .filter(client__in=clients)
        .select_related("client", "stage")
        .order_by("-updated_at")[:50]
    )
    # Открытые обращения выше закрытых.
    ordered = sorted(leads, key=lambda lead: lead.stage.kind != PipelineStage.Kind.OPEN)
    return ordered[:limit]
