"""Изменение обращения по полям (Strategy).

Каждое правило отвечает за одно поле: проверяет вход, применяет изменение и
возвращает строку для истории. Новое редактируемое поле добавляется классом
в LEAD_FIELD_RULES, без правки update_lead.
"""

from dataclasses import dataclass
from typing import Protocol

from crm.core.errors import ApiError
from crm.core.validation import clean_text, optional, optional_aware_datetime
from crm.organizations.models import Membership
from crm.organizations.permissions import Perm, require

from .models import Lead, PipelineStage
from .pipeline import find_stage


@dataclass(frozen=True)
class ChangeContext:
    member: Membership
    company_id: object
    resolve_assignee: object  # callable(company_id, value) -> Membership


class LeadFieldRule(Protocol):
    def apply(self, lead: Lead, data: dict, ctx: ChangeContext) -> list[str]: ...


class StageRule:
    """Переход в активный этап воронки компании; отказ требует причины."""

    def apply(self, lead, data, ctx):
        stage = lead.stage
        if "stage" in data and str(data["stage"]) != str(lead.stage_id):
            stage = find_stage(ctx.company_id, data["stage"])
        reason = (
            optional(data, "refusal_reason", 500)
            if "refusal_reason" in data
            else lead.refusal_reason
        )
        refused = stage.kind == PipelineStage.Kind.REFUSED
        if refused and not reason:
            raise ApiError("Укажите причину отказа.")
        changes = []
        if stage.pk != lead.stage_id:
            changes.append(f"Этап: {lead.stage.name} → {stage.name}")
        if refused and reason != lead.refusal_reason:
            changes.append(f"Причина отказа: {reason}")
        lead.stage = stage
        lead.refusal_reason = reason if refused else ""
        return changes


class AssigneeRule:
    def apply(self, lead, data, ctx):
        if "assignee_id" not in data or str(data["assignee_id"]) == str(
            lead.assignee_id
        ):
            return []
        require(ctx.member, Perm.ASSIGN_LEADS)
        lead.assignee = ctx.resolve_assignee(ctx.company_id, data["assignee_id"])
        return [f"Ответственный: {lead.assignee.user.name}"]


class NextContactRule:
    def apply(self, lead, data, ctx):
        if "next_contact_at" not in data:
            return []
        value = optional_aware_datetime(
            data["next_contact_at"], "Укажите дату и время с часовым поясом."
        )
        if value == lead.next_contact_at:
            return []
        lead.next_contact_at = value
        return ["Обновлено время следующего контакта"]


@dataclass(frozen=True)
class TextRule:
    field: str
    label: str
    max_length: int
    required: bool
    history: str

    def apply(self, lead, data, ctx):
        if self.field not in data:
            return []
        value = (
            clean_text(data[self.field], self.label, self.max_length)
            if self.required
            else optional(data, self.field, self.max_length)
        )
        if value == getattr(lead, self.field):
            return []
        setattr(lead, self.field, value)
        return [self.history]


LEAD_FIELD_RULES: tuple[LeadFieldRule, ...] = (
    StageRule(),
    AssigneeRule(),
    NextContactRule(),
    TextRule("title", "Название обращения", 240, True, "Обновлено название обращения"),
    TextRule("source", "Источник", 120, False, "Обновлён источник"),
)


def apply_changes(lead, data, ctx, rules=LEAD_FIELD_RULES):
    changes = []
    for rule in rules:
        changes.extend(rule.apply(lead, data, ctx))
    return changes
