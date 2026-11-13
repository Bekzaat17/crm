from crm.core.errors import ApiError
from crm.sales.selectors import leads_for

from .models import AdmissionTransfer, RehubCenter


def find_center(company_id, center_id, lock=False):
    queryset = RehubCenter.objects.filter(organization_id=company_id, pk=center_id)
    if lock:
        queryset = queryset.select_for_update()
    center = queryset.first()
    if not center:
        raise ApiError("Центр не найден.", 404)
    return center


def company_centers(company_id):
    return RehubCenter.objects.filter(organization_id=company_id).order_by("name")


def destinations(company_id):
    return company_centers(company_id).filter(is_active=True, verified_at__isnull=False)


def transfers_for(member, lead_id):
    if not leads_for(member).filter(pk=lead_id).exists():
        raise ApiError("Обращение не найдено.", 404)
    return (
        AdmissionTransfer.objects.filter(lead_id=lead_id)
        .select_related("center")
        .order_by("-created_at")
    )
