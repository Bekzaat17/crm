"""Отчёт по обращениям компании.

Область данных задаёт стратегия роли (leads_for): менеджер видит только свои
обращения, руководитель и администратор — все. Когорта — обращения, созданные
за период; динамика — события (создание, поступление, отказ) по их дате.
"""

from collections import Counter, defaultdict
from statistics import median

from django.db.models import Count, F, Q
from django.utils import timezone

from crm.core.validation import identifier
from crm.organizations.models import Branch, Membership
from crm.organizations.permissions import Perm, can
from crm.sales.models import LeadStageChange, PipelineStage
from crm.sales.selectors import leads_for
from crm.work.models import FollowUpTask

from .period import Period

Kind = PipelineStage.Kind
NO_SOURCE = "Не указан"
OTHER = "Другие"
TOP_SOURCES = 10
TOP_REASONS = 8


def _scoped_leads(member, query):
    leads = leads_for(member)
    if query.get("branch"):
        leads = leads.filter(branch_id=identifier(query["branch"]))
    if query.get("assignee") and can(member, Perm.VIEW_ALL_LEADS):
        leads = leads.filter(assignee_id=identifier(query["assignee"]))
    return leads


def _created_in(leads, period: Period):
    return leads.filter(created_at__gte=period.start, created_at__lt=period.end)


def _rate(part, whole):
    return round(part / whole, 4) if whole else None


def _days(changes_at, created_at):
    return (changes_at - created_at).total_seconds() / 86400


def _top(counter, limit):
    ordered = counter.most_common()
    head, tail = ordered[:limit], ordered[limit:]
    if tail:
        head.append((OTHER, sum(count for _, count in tail)))
    return head


class Report:
    def __init__(self, member, period: Period, query):
        self.member = member
        self.period = period
        self.company_id = member.organization_id
        self.see_all = can(member, Perm.VIEW_ALL_LEADS)
        self.leads = _scoped_leads(member, query)
        self.cohort = list(
            _created_in(self.leads, period).values(
                "id",
                "source",
                "refusal_reason",
                "assignee_id",
                "created_at",
                kind=F("stage__kind"),
            )
        )
        self.changes = defaultdict(list)
        for change in (
            LeadStageChange.objects.filter(lead__in=_created_in(self.leads, period))
            .order_by("at", "id")
            .values("lead_id", "to_stage_id", "at", kind=F("to_stage__kind"))
        ):
            self.changes[change["lead_id"]].append(change)

    # Когорта

    def _admission_days(self, leads):
        days = []
        for lead in leads:
            if lead["kind"] != Kind.ADMITTED:
                continue
            first = next(
                (c for c in self.changes[lead["id"]] if c["kind"] == Kind.ADMITTED),
                None,
            )
            if first:
                days.append(_days(first["at"], lead["created_at"]))
        return round(median(days), 1) if days else None

    def _outcome(self, leads):
        kinds = Counter(lead["kind"] for lead in leads)
        created = len(leads)
        return {
            "created": created,
            "open": kinds[Kind.OPEN],
            "admitted": kinds[Kind.ADMITTED],
            "refused": kinds[Kind.REFUSED],
            "conversion": _rate(kinds[Kind.ADMITTED], created),
            "median_days_to_admission": self._admission_days(leads),
        }

    def previous(self):
        totals = _created_in(self.leads, self.period.previous()).aggregate(
            created=Count("id"),
            admitted=Count("id", filter=Q(stage__kind=Kind.ADMITTED)),
            refused=Count("id", filter=Q(stage__kind=Kind.REFUSED)),
        )
        totals["conversion"] = _rate(totals["admitted"], totals["created"])
        return totals

    def funnel(self):
        """Сколько обращений дошло хотя бы до этапа. Поступившие считаются
        прошедшими все открытые этапы; последний шаг — поступившие сейчас."""
        stages = list(
            PipelineStage.objects.filter(
                organization_id=self.company_id, is_active=True, kind=Kind.OPEN
            ).order_by("position")
        )
        if not stages:
            return []
        position = {stage.pk: stage.position for stage in stages}
        reached = Counter()
        admitted = 0
        for lead in self.cohort:
            if lead["kind"] == Kind.ADMITTED:
                admitted += 1
                continue
            visited = [
                position[c["to_stage_id"]]
                for c in self.changes[lead["id"]]
                if c["to_stage_id"] in position
            ]
            reached[max(visited, default=stages[0].position)] += 1
        steps = []
        for stage in stages:
            count = admitted + sum(
                n for pos, n in reached.items() if pos >= stage.position
            )
            steps.append(
                {
                    "id": str(stage.pk),
                    "name": stage.name,
                    "color": stage.color,
                    "kind": stage.kind,
                    "count": count,
                }
            )
        steps.append(
            {
                "id": "admitted",
                "name": "Поступили",
                "color": "",
                "kind": Kind.ADMITTED,
                "count": admitted,
            }
        )
        return steps

    def sources(self):
        created, admitted = Counter(), Counter()
        for lead in self.cohort:
            name = lead["source"].strip() or NO_SOURCE
            created[name] += 1
            admitted[name] += lead["kind"] == Kind.ADMITTED
        top = _top(created, TOP_SOURCES)
        named = {name for name, _ in top if name != OTHER}
        rows = []
        for name, count in top:
            won = (
                sum(n for key, n in admitted.items() if key not in named)
                if name == OTHER
                else admitted[name]
            )
            rows.append(
                {
                    "name": name,
                    "created": count,
                    "admitted": won,
                    "conversion": _rate(won, count),
                }
            )
        return rows

    def refusal_reasons(self):
        labels, counts = {}, Counter()
        for lead in self.cohort:
            if lead["kind"] != Kind.REFUSED:
                continue
            text = " ".join(lead["refusal_reason"].split()) or NO_SOURCE
            key = text.casefold()
            labels.setdefault(key, text)
            counts[key] += 1
        return [
            {"reason": labels.get(key, OTHER), "count": count}
            for key, count in _top(counts, TOP_REASONS)
        ]

    # Динамика

    def series(self):
        buckets = {day: Counter() for day in self.period.buckets()}
        for lead in self.cohort:
            buckets[self.period.bucket_of(lead["created_at"])]["created"] += 1
        events = (
            LeadStageChange.objects.filter(
                lead__in=self.leads,
                at__gte=self.period.start,
                at__lt=self.period.end,
                to_stage__kind__in=[Kind.ADMITTED, Kind.REFUSED],
            )
            .exclude(from_stage__kind=F("to_stage__kind"))
            .values("at", kind=F("to_stage__kind"))
        )
        for event in events:
            buckets[self.period.bucket_of(event["at"])][event["kind"]] += 1
        return [
            {
                "start": day.isoformat(),
                "created": counts["created"],
                "admitted": counts[Kind.ADMITTED],
                "refused": counts[Kind.REFUSED],
            }
            for day, counts in buckets.items()
        ]

    # Команда

    def _members(self):
        return {
            m.pk: m
            for m in Membership.objects.select_related("user")
            .filter(organization_id=self.company_id)
            .filter(
                Q(is_active=True)
                | Q(pk__in={lead["assignee_id"] for lead in self.cohort})
            )
        }

    def team(self):
        if not self.see_all:
            return None
        by_member = defaultdict(list)
        for lead in self.cohort:
            by_member[lead["assignee_id"]].append(lead)
        overdue = dict(
            FollowUpTask.objects.filter(
                lead__in=self.leads,
                completed_at__isnull=True,
                due_at__lte=timezone.now(),
            )
            .values_list("lead__assignee_id")
            .annotate(n=Count("id"))
        )
        rows = [
            {
                "id": str(pk),
                "name": member.user.name,
                "is_active": member.is_active,
                "overdue_tasks": overdue.get(pk, 0),
                **self._outcome(by_member[pk]),
            }
            for pk, member in self._members().items()
        ]
        return sorted(rows, key=lambda r: (-r["created"], r["name"].casefold()))

    def filters(self):
        branches = Branch.objects.filter(organization_id=self.company_id).order_by(
            "-is_active", "name"
        )
        result = {
            "branches": [
                {"id": str(b.pk), "name": b.name, "is_active": b.is_active}
                for b in branches
            ],
            "assignees": [],
        }
        if self.see_all:
            members = Membership.objects.select_related("user").filter(
                organization_id=self.company_id, is_active=True
            )
            result["assignees"] = sorted(
                ({"id": str(m.pk), "name": m.user.name} for m in members),
                key=lambda m: m["name"].casefold(),
            )
        return result

    def data(self):
        return {
            "period": {
                "from": self.period.first.isoformat(),
                "to": self.period.last.isoformat(),
                "bucket": self.period.bucket,
            },
            "scope": "company" if self.see_all else "own",
            "filters": self.filters(),
            "totals": self._outcome(self.cohort),
            "previous": self.previous(),
            "funnel": self.funnel(),
            "series": self.series(),
            "sources": self.sources(),
            "refusal_reasons": self.refusal_reasons(),
            "team": self.team(),
        }
