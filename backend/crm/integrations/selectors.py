from crm.models import AdmissionTransfer, RehubCenter
from crm.sales.selectors import leads_for
from crm.services import ApiError, get_membership, require_team_admin


def admin_membership(actor, company_id):
    member = get_membership(actor, company_id)
    require_team_admin(member)
    return member


def find_center(company_id, center_id, lock=False):
    queryset = RehubCenter.objects.filter(organization_id=company_id, pk=center_id)
    if lock:
        queryset = queryset.select_for_update()
    center = queryset.first()
    if not center:
        raise ApiError("Центр не найден.", 404)
    return center


def transfers_for(member, lead_id):
    if not leads_for(member).filter(pk=lead_id).exists():
        raise ApiError("Обращение не найдено.", 404)
    return (
        AdmissionTransfer.objects.filter(lead_id=lead_id)
        .select_related("center")
        .order_by("-created_at")
    )


def require_sender(member):
    if member.role not in ("owner", "admin", "lead"):
        raise ApiError(
            "Подтвердить передачу может владелец, администратор или руководитель.", 403
        )
