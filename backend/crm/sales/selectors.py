"""Правила видимости обращений и карточек. Область задаёт политика роли."""

from crm.core.errors import ApiError
from crm.organizations.permissions import policy_for

from .models import Client, Lead

PAGE_SIZE = 50


def leads_for(member):
    queryset = Lead.objects.filter(organization_id=member.organization_id)
    return policy_for(member).scope.leads(member, queryset)


def clients_for(member):
    queryset = Client.objects.filter(organization_id=member.organization_id)
    return policy_for(member).scope.clients(member, queryset)


def find_client(member, pk, lock=False):
    # distinct + FOR UPDATE не поддерживается PostgreSQL: сначала проверяем область доступа.
    if not clients_for(member).filter(pk=pk).exists():
        raise ApiError("Клиент не найден.", 404)
    queryset = Client.objects.filter(pk=pk, organization_id=member.organization_id)
    return queryset.select_for_update().get() if lock else queryset.get()


def find_lead(member, pk, lock=False):
    queryset = leads_for(member)
    if lock:
        queryset = queryset.select_for_update()
    lead = queryset.filter(pk=pk).first()
    if not lead:
        raise ApiError("Обращение не найдено.", 404)
    return lead


def page(queryset, value):
    try:
        number = int(value)
        if number < 1 or number > 100000:
            raise ValueError
    except ValueError:
        raise ApiError("Некорректный номер страницы.")
    total = queryset.count()
    start = (number - 1) * PAGE_SIZE
    rows = list(queryset[start : start + PAGE_SIZE])
    return rows, total, number * PAGE_SIZE < total
