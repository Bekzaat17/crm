from django.db.models import Q

from crm.models import Client, Lead
from crm.services import ApiError


def leads_for(member):
    qs = Lead.objects.filter(organization_id=member.organization_id)
    return qs.filter(assignee=member) if member.role == "manager" else qs


def clients_for(member):
    qs = Client.objects.filter(organization_id=member.organization_id)
    if member.role == "manager":
        qs = qs.filter(
            Q(leads__assignee=member) | Q(created_by=member.user, leads__isnull=True)
        ).distinct()
    return qs


def find_client(member, pk, lock=False):
    # distinct + FOR UPDATE не поддерживается PostgreSQL: сначала проверяем область доступа.
    if not clients_for(member).filter(pk=pk).exists():
        raise ApiError("Клиент не найден.", 404)
    qs = Client.objects.filter(pk=pk, organization_id=member.organization_id)
    return qs.select_for_update().get() if lock else qs.get()


def find_lead(member, pk, lock=False):
    qs = leads_for(member)
    if lock:
        qs = qs.select_for_update()
    obj = qs.filter(pk=pk).first()
    if not obj:
        raise ApiError("Обращение не найдено.", 404)
    return obj


def page(qs, value):
    try:
        number = int(value)
        if number < 1 or number > 100000:
            raise ValueError
    except ValueError:
        raise ApiError("Некорректный номер страницы.")
    total = qs.count()
    return list(qs[(number - 1) * 50 : number * 50]), total, number * 50 < total
