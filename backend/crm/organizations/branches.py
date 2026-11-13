"""Филиалы компании. Филиал с обращениями не удаляется, а архивируется."""

from django.db import transaction

from crm.core.errors import ApiError
from crm.core.validation import clean_text, identifier

from . import audit
from .context import get_membership
from .models import Branch
from .permissions import Perm

MAX_BRANCHES = 100


def company_branches(company_id, include_archived=False):
    queryset = Branch.objects.filter(organization_id=company_id)
    if not include_archived:
        queryset = queryset.filter(is_active=True)
    return queryset.order_by("-is_active", "name")


def find_branch(company_id, branch_id, lock=False, active=None):
    queryset = Branch.objects.filter(
        organization_id=company_id, pk=identifier(branch_id)
    )
    if active is not None:
        queryset = queryset.filter(is_active=active)
    if lock:
        queryset = queryset.select_for_update()
    branch = queryset.first()
    if not branch:
        raise ApiError("Филиал не найден.", 404)
    return branch


def _unique_name(company_id, name, excluding=None):
    # casefold в Python: SQLite не сравнивает кириллицу без учёта регистра.
    others = Branch.objects.filter(organization_id=company_id).exclude(pk=excluding)
    if any(
        n.casefold() == name.casefold() for n in others.values_list("name", flat=True)
    ):
        raise ApiError("Филиал с таким названием уже есть.", 409)
    return name


@transaction.atomic
def create_branch(actor, company_id, data):
    get_membership(actor, company_id, Perm.MANAGE_BRANCHES, lock=True)
    if Branch.objects.filter(organization_id=company_id).count() >= MAX_BRANCHES:
        raise ApiError(f"У компании может быть не более {MAX_BRANCHES} филиалов.")
    name = clean_text(data.get("name"), "Название филиала", 160)
    branch = Branch.objects.create(
        organization_id=company_id, name=_unique_name(company_id, name)
    )
    audit.record(company_id, actor, "branch.created", branch.id)
    return branch


@transaction.atomic
def rename_branch(actor, company_id, branch_id, data):
    get_membership(actor, company_id, Perm.MANAGE_BRANCHES, lock=True)
    branch = find_branch(company_id, branch_id, lock=True)
    if data.get("version") != branch.version:
        raise ApiError("Филиал изменился. Обновите список.", 409)
    name = clean_text(data.get("name"), "Название филиала", 160)
    branch.name = _unique_name(company_id, name, branch.pk)
    branch.version += 1
    branch.save(update_fields=["name", "version"])
    audit.record(company_id, actor, "branch.updated", branch.id)
    return branch


@transaction.atomic
def set_branch_active(actor, company_id, branch_id, active):
    get_membership(actor, company_id, Perm.MANAGE_BRANCHES, lock=True)
    branch = find_branch(company_id, branch_id, lock=True)
    if branch.is_active == active:
        return branch
    if not active and not company_branches(company_id).exclude(pk=branch.pk).exists():
        raise ApiError("Нельзя архивировать последний действующий филиал.", 409)
    branch.is_active = active
    branch.version += 1
    branch.save(update_fields=["is_active", "version"])
    audit.record(
        company_id, actor, "branch.restored" if active else "branch.archived", branch.id
    )
    return branch
