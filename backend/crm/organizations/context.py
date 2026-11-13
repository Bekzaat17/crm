from crm.core.errors import ApiError

from .models import Membership, Organization
from .permissions import Perm, require


def _active_membership(user, organization_id):
    membership = (
        Membership.objects.select_related("organization", "user")
        .filter(user=user, organization_id=organization_id, is_active=True)
        .first()
    )
    if not membership:
        raise ApiError("Компания не найдена или доступ закрыт.", 404)
    return membership


def get_membership(user, organization_id, perm: Perm | None = None, lock=False):
    """Единственная точка входа в данные компании.

    lock=True сериализует операцию с изменениями состава компании: компания
    блокируется до конца транзакции, после блокировки членство перечитывается.
    """
    membership = _active_membership(user, organization_id)
    if lock:
        Organization.objects.select_for_update().get(pk=organization_id)
        membership = _active_membership(user, organization_id)
    if perm is not None:
        require(membership, perm)
    return membership
