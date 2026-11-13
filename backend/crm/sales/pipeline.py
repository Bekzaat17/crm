"""Настройка этапов воронки компании.

Инварианты:
- у компании всегда есть активный этап каждого типа (open, admitted, refused);
- этап с обращениями не удаляется: при архивировании обращения переносятся
  в активный этап того же типа, с записью в историю;
- тип этапа с обращениями не меняется — иначе изменился бы смысл их истории.
"""

import re

from django.db import transaction
from django.db.models import Count, F
from django.utils import timezone

from crm.core.errors import ApiError
from crm.core.validation import clean_text, identifier, require_version, unique_name
from crm.organizations import audit
from crm.organizations.context import get_membership
from crm.organizations.permissions import Perm

from .models import Lead, LeadActivity, LeadStageChange, PipelineStage

Kind = PipelineStage.Kind
MAX_STAGES = 30
DEFAULT_STAGES = (
    ("Новое", Kind.OPEN, "#64748b"),
    ("В работе", Kind.OPEN, "#2563eb"),
    ("Консультация", Kind.OPEN, "#7c3aed"),
    ("Ожидаем поступление", Kind.OPEN, "#d97706"),
    ("Поступил", Kind.ADMITTED, "#16a34a"),
    ("Отказ", Kind.REFUSED, "#dc2626"),
)


def create_default_stages(organization):
    PipelineStage.objects.bulk_create(
        PipelineStage(
            organization=organization,
            name=name,
            kind=kind,
            color=color,
            position=position,
        )
        for position, (name, kind, color) in enumerate(DEFAULT_STAGES)
    )


def active_stages(company_id):
    return PipelineStage.objects.filter(
        organization_id=company_id, is_active=True
    ).order_by("position", "created_at")


def all_stages(company_id):
    return (
        PipelineStage.objects.filter(organization_id=company_id)
        .annotate(lead_count=Count("leads"))
        .order_by("-is_active", "position", "created_at")
    )


def find_stage(company_id, value, lock=False, active=True):
    queryset = PipelineStage.objects.filter(
        organization_id=company_id, pk=identifier(value)
    )
    if active:
        queryset = queryset.filter(is_active=True)
    if lock:
        queryset = queryset.select_for_update()
    stage = queryset.first()
    if not stage:
        raise ApiError("Этап не найден в воронке компании.", 404)
    return stage


def initial_stage(company_id):
    stage = active_stages(company_id).filter(kind=Kind.OPEN).first()
    if not stage:
        raise ApiError("Добавьте в воронку хотя бы один открытый этап.", 409)
    return stage


def _name(data):
    return clean_text(data.get("name"), "Название этапа", 80)


def _kind(value):
    if value not in Kind.values:
        raise ApiError("Выберите тип этапа: в работе, поступил или отказ.")
    return value


def _color(value):
    if value in (None, ""):
        return ""
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ApiError("Цвет этапа укажите в формате #RRGGBB.")
    return value.lower()


def _require_kind_remains(company_id, kind, excluding):
    if not active_stages(company_id).filter(kind=kind).exclude(pk=excluding).exists():
        raise ApiError(
            f"В воронке должен остаться активный этап типа «{Kind(kind).label}».", 409
        )


def _unique(company_id, name, excluding=None):
    others = active_stages(company_id).exclude(pk=excluding)
    return unique_name(
        name,
        others.values_list("name", flat=True),
        "Активный этап с таким названием уже есть.",
    )


@transaction.atomic
def create_stage(actor, company_id, data):
    get_membership(actor, company_id, Perm.MANAGE_PIPELINE, lock=True)
    if active_stages(company_id).count() >= MAX_STAGES:
        raise ApiError(f"В воронке может быть не более {MAX_STAGES} этапов.")
    last = active_stages(company_id).order_by("-position").first()
    stage = PipelineStage.objects.create(
        organization_id=company_id,
        name=_unique(company_id, _name(data)),
        kind=_kind(data.get("kind", Kind.OPEN)),
        color=_color(data.get("color")),
        position=(last.position + 1) if last else 0,
    )
    audit.record(company_id, actor, "stage.created", stage.id)
    return stage


@transaction.atomic
def update_stage(actor, company_id, stage_id, data):
    get_membership(actor, company_id, Perm.MANAGE_PIPELINE, lock=True)
    stage = find_stage(company_id, stage_id, lock=True)
    require_version(stage, data, "Этап изменился. Обновите настройки воронки.")
    if "name" in data:
        stage.name = _unique(company_id, _name(data), stage.pk)
    if "color" in data:
        stage.color = _color(data["color"])
    if "kind" in data and _kind(data["kind"]) != stage.kind:
        if stage.leads.exists():
            raise ApiError(
                "Тип этапа с обращениями менять нельзя. Создайте новый этап.", 409
            )
        _require_kind_remains(company_id, stage.kind, stage.pk)
        stage.kind = data["kind"]
    stage.version += 1
    stage.save()
    audit.record(company_id, actor, "stage.updated", stage.id)
    return stage


@transaction.atomic
def reorder_stages(actor, company_id, data):
    get_membership(actor, company_id, Perm.MANAGE_PIPELINE, lock=True)
    ids = data.get("ids")
    stages = {str(s.id): s for s in active_stages(company_id)}
    if not isinstance(ids, list) or sorted(map(str, ids)) != sorted(stages):
        raise ApiError("Передайте полный список активных этапов в новом порядке.")
    for position, stage_id in enumerate(ids):
        stage = stages[str(stage_id)]
        if stage.position != position:
            stage.position = position
            stage.version += 1
            stage.save(update_fields=["position", "version"])
    audit.record(company_id, actor, "stage.reordered")
    return list(active_stages(company_id))


@transaction.atomic
def archive_stage(actor, company_id, stage_id, data):
    get_membership(actor, company_id, Perm.MANAGE_PIPELINE, lock=True)
    stage = find_stage(company_id, stage_id, lock=True)
    _require_kind_remains(company_id, stage.kind, stage.pk)
    leads = Lead.objects.select_for_update().filter(stage=stage)
    moved = list(leads.values_list("pk", flat=True))
    if moved:
        if not data.get("move_to"):
            raise ApiError("Выберите этап, в который перенести обращения.")
        target = find_stage(company_id, data["move_to"])
        if target.pk == stage.pk or target.kind != stage.kind:
            raise ApiError("Обращения можно перенести только в этап того же типа.")
        # bulk update не трогает auto_now: перенесённые обращения поднимаются на доске.
        Lead.objects.filter(pk__in=moved).update(
            stage=target, version=F("version") + 1, updated_at=timezone.now()
        )
        LeadActivity.objects.bulk_create(
            LeadActivity(
                lead_id=pk,
                actor=actor,
                kind="changed",
                text=f"Этап: {stage.name} → {target.name} (этап архивирован)",
            )
            for pk in moved
        )
        LeadStageChange.objects.bulk_create(
            LeadStageChange(lead_id=pk, from_stage=stage, to_stage=target, actor=actor)
            for pk in moved
        )
    stage.is_active = False
    stage.version += 1
    stage.save(update_fields=["is_active", "version"])
    audit.record(company_id, actor, "stage.archived", stage.id)
    return stage, len(moved)


@transaction.atomic
def restore_stage(actor, company_id, stage_id):
    get_membership(actor, company_id, Perm.MANAGE_PIPELINE, lock=True)
    stage = find_stage(company_id, stage_id, lock=True, active=False)
    if stage.is_active:
        return stage
    if active_stages(company_id).count() >= MAX_STAGES:
        raise ApiError(f"В воронке может быть не более {MAX_STAGES} этапов.")
    _unique(company_id, stage.name)
    last = active_stages(company_id).order_by("-position").first()
    stage.is_active = True
    stage.position = (last.position + 1) if last else 0
    stage.version += 1
    stage.save(update_fields=["is_active", "position", "version"])
    audit.record(company_id, actor, "stage.restored", stage.id)
    return stage
