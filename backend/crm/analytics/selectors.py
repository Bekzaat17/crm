"""Отчёт центра за период: сколько обратились, поступили и отказались.

Все цифры — события периода: обращение создано, клиент поступил, клиент
отказался. Область данных задаёт стратегия роли (leads_for): менеджер видит
только свои обращения, руководитель и администратор — все.
"""

from collections import Counter

from django.db.models import Count, F
from django.utils import timezone

from crm.core.validation import identifier
from crm.organizations.models import Membership
from crm.organizations.permissions import Perm, can
from crm.sales.models import LeadStageChange, PipelineStage
from crm.sales.selectors import leads_for
from crm.work.models import FollowUpTask

from .period import Period

Kind = PipelineStage.Kind
NO_SOURCE = "Не указан"
NO_REASON = "Без причины"
OTHER = "Другие"
TOP = 8


def _rate(part, whole):
    return round(part / whole, 4) if whole else None


def _top(counter):
    ordered = counter.most_common()
    head, tail = ordered[:TOP], ordered[TOP:]
    if tail:
        head.append((OTHER, sum(count for _, count in tail)))
    return head


def _clean(text, empty):
    return " ".join(text.split()) or empty


class Report:
    def __init__(self, member, period: Period, query):
        self.member = member
        self.period = period
        self.see_all = can(member, Perm.VIEW_ALL_LEADS)
        leads = leads_for(member)
        if query.get("assignee") and self.see_all:
            leads = leads.filter(assignee_id=identifier(query["assignee"]))
        self.leads = leads
        self.created = list(
            leads.filter(
                created_at__gte=period.start, created_at__lt=period.end
            ).values("created_at", "source", "assignee_id")
        )
        self.admitted = self._outcomes(Kind.ADMITTED)
        self.refused = self._outcomes(Kind.REFUSED)

    def _outcomes(self, kind):
        """Первый за период переход обращения в этап типа kind."""
        first = {}
        changes = (
            LeadStageChange.objects.filter(
                lead__in=self.leads,
                at__gte=self.period.start,
                at__lt=self.period.end,
                to_stage__kind=kind,
            )
            .exclude(from_stage__kind=kind)
            .order_by("at", "id")
            .values(
                "lead_id",
                "at",
                source=F("lead__source"),
                assignee_id=F("lead__assignee_id"),
                reason=F("lead__refusal_reason"),
            )
        )
        for change in changes:
            first.setdefault(change["lead_id"], change)
        return list(first.values())

    def totals(self):
        created, admitted = len(self.created), len(self.admitted)
        return {
            "created": created,
            "admitted": admitted,
            "refused": len(self.refused),
            "conversion": _rate(admitted, created),
        }

    def series(self):
        buckets = {day: Counter() for day in self.period.buckets()}
        for lead in self.created:
            buckets[self.period.bucket_of(lead["created_at"])]["created"] += 1
        for change in self.admitted:
            buckets[self.period.bucket_of(change["at"])]["admitted"] += 1
        return [
            {
                "start": day.isoformat(),
                "created": c["created"],
                "admitted": c["admitted"],
            }
            for day, c in buckets.items()
        ]

    def sources(self):
        created = Counter(_clean(lead["source"], NO_SOURCE) for lead in self.created)
        admitted = Counter(_clean(c["source"], NO_SOURCE) for c in self.admitted)
        names = created + admitted
        top = _top(names)
        named = {name for name, _ in top if name != OTHER}
        rows = []
        for name, _ in top:
            pick = (
                (lambda n: n not in named) if name == OTHER else (lambda n: n == name)
            )
            rows.append(
                {
                    "name": name,
                    "created": sum(v for n, v in created.items() if pick(n)),
                    "admitted": sum(v for n, v in admitted.items() if pick(n)),
                }
            )
        return rows

    def refusal_reasons(self):
        labels, counts = {}, Counter()
        for change in self.refused:
            text = _clean(change["reason"], NO_REASON)
            labels.setdefault(text.casefold(), text)
            counts[text.casefold()] += 1
        return [
            {"reason": labels.get(key, OTHER), "count": count}
            for key, count in _top(counts)
        ]

    def team(self):
        if not self.see_all:
            return None
        created = Counter(lead["assignee_id"] for lead in self.created)
        admitted = Counter(c["assignee_id"] for c in self.admitted)
        refused = Counter(c["assignee_id"] for c in self.refused)
        overdue = dict(
            FollowUpTask.objects.filter(
                lead__in=self.leads,
                completed_at__isnull=True,
                due_at__lte=timezone.now(),
            )
            .values_list("lead__assignee_id")
            .annotate(n=Count("id"))
        )
        involved = set(created) | set(admitted) | set(refused) | set(overdue)
        members = Membership.objects.select_related("user").filter(
            organization_id=self.member.organization_id
        )
        rows = [
            {
                "id": str(m.pk),
                "name": m.user.name,
                "created": created[m.pk],
                "admitted": admitted[m.pk],
                "refused": refused[m.pk],
                "conversion": _rate(admitted[m.pk], created[m.pk]),
                "overdue_tasks": overdue.get(m.pk, 0),
            }
            for m in members
            if m.is_active or m.pk in involved
        ]
        return sorted(rows, key=lambda r: (-r["admitted"], -r["created"], r["name"]))

    def assignees(self):
        if not self.see_all:
            return []
        members = Membership.objects.select_related("user").filter(
            organization_id=self.member.organization_id, is_active=True
        )
        return sorted(
            ({"id": str(m.pk), "name": m.user.name} for m in members),
            key=lambda m: m["name"].casefold(),
        )

    def data(self):
        return {
            "period": {
                "from": self.period.first.isoformat(),
                "to": self.period.last.isoformat(),
                "bucket": self.period.bucket,
            },
            "scope": "company" if self.see_all else "own",
            "assignees": self.assignees(),
            "totals": self.totals(),
            "series": self.series(),
            "sources": self.sources(),
            "refusal_reasons": self.refusal_reasons(),
            "team": self.team(),
        }
