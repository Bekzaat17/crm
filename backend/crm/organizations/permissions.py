"""Права ролей компании.

Роль хранится в Membership и определяет политику (Strategy): набор прав и
область видимости обращений. Новая роль добавляется записью в POLICIES,
без правок проверок в сервисах и выборках.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from django.db.models import Q, QuerySet

from crm.core.errors import ApiError

from .models import Membership


class Perm(str, Enum):
    MANAGE_TEAM = "manage_team"
    MANAGE_ROLES = "manage_roles"
    MANAGE_BRANCHES = "manage_branches"
    MANAGE_PIPELINE = "manage_pipeline"
    MANAGE_CENTERS = "manage_centers"
    VIEW_AUDIT = "view_audit"
    VIEW_ALL_LEADS = "view_all_leads"
    ASSIGN_LEADS = "assign_leads"
    SEND_ADMISSIONS = "send_admissions"
    TRANSFER_OWNERSHIP = "transfer_ownership"


DENIED = {
    Perm.MANAGE_TEAM: "Управлять командой может владелец или администратор.",
    Perm.MANAGE_ROLES: "Менять роли может владелец или администратор.",
    Perm.MANAGE_BRANCHES: "Управлять филиалами может владелец или администратор.",
    Perm.MANAGE_PIPELINE: "Настраивать воронку может владелец или администратор.",
    Perm.MANAGE_CENTERS: "Управлять центрами может владелец или администратор.",
    Perm.VIEW_AUDIT: "Историю действий видят владелец и администратор.",
    Perm.VIEW_ALL_LEADS: "Недостаточно прав для просмотра обращений компании.",
    Perm.ASSIGN_LEADS: "Менеджер не может переназначать обращения.",
    Perm.SEND_ADMISSIONS: (
        "Подтвердить передачу может владелец, администратор или руководитель."
    ),
    Perm.TRANSFER_OWNERSHIP: "Передать владение может только владелец.",
}


class LeadScope(Protocol):
    """Стратегия видимости обращений и карточек клиентов сотрудника."""

    def leads(self, member: Membership, queryset: QuerySet) -> QuerySet: ...

    def clients(self, member: Membership, queryset: QuerySet) -> QuerySet: ...


class CompanyScope:
    def leads(self, member, queryset):
        return queryset

    def clients(self, member, queryset):
        return queryset


class AssignedScope:
    """Свои обращения, их карточки и собственные карточки без обращений."""

    def leads(self, member, queryset):
        return queryset.filter(assignee=member)

    def clients(self, member, queryset):
        return queryset.filter(
            Q(leads__assignee=member) | Q(created_by=member.user, leads__isnull=True)
        ).distinct()


@dataclass(frozen=True)
class RolePolicy:
    permissions: frozenset
    scope: LeadScope
    # Роли сотрудников, которых эта роль может приглашать, назначать и отключать.
    manageable_roles: frozenset = frozenset()

    def can(self, perm: Perm) -> bool:
        return perm in self.permissions

    def manages(self, role) -> bool:
        return role in self.manageable_roles


_ALL = frozenset(Perm)
_LEAD = frozenset({Perm.VIEW_ALL_LEADS, Perm.ASSIGN_LEADS, Perm.SEND_ADMISSIONS})

_STAFF = frozenset({Membership.Role.LEAD, Membership.Role.MANAGER})

POLICIES = {
    Membership.Role.OWNER: RolePolicy(
        _ALL, CompanyScope(), _STAFF | {Membership.Role.ADMIN}
    ),
    Membership.Role.ADMIN: RolePolicy(
        _ALL - {Perm.TRANSFER_OWNERSHIP}, CompanyScope(), _STAFF
    ),
    Membership.Role.LEAD: RolePolicy(_LEAD, CompanyScope()),
    Membership.Role.MANAGER: RolePolicy(frozenset(), AssignedScope()),
}


def policy_for(member: Membership) -> RolePolicy:
    return POLICIES[Membership.Role(member.role)]


def can(member: Membership, perm: Perm) -> bool:
    return policy_for(member).can(perm)


def require(member: Membership, perm: Perm, message: str | None = None):
    if not can(member, perm):
        raise ApiError(message or DENIED[perm], 403)


def require_manages(member: Membership, role, message: str):
    """Владелец управляет всеми сотрудниками, администратор — руководителями
    и менеджерами. Роль владельца назначается только передачей владения."""
    if not policy_for(member).manages(role):
        raise ApiError(message, 403)


def assignable_roles(member: Membership) -> list[str]:
    return [r.value for r in Membership.Role if policy_for(member).manages(r)]


def granted(member: Membership) -> list[str]:
    return sorted(p.value for p in policy_for(member).permissions)
