from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from crm.analytics.period import Period
from crm.models import Lead, LeadStageChange
from crm.tests.test_sales import SalesFixtures
from crm.work.models import FollowUpTask


class AnalyticsTests(SalesFixtures):
    def report(self, query=""):
        return self.client.get(f"/api/{self.url('analytics')}/{query}")

    def move(self, lead, stage, **extra):
        lead.refresh_from_db()
        response = self.post(
            self.url(f"leads/{lead.id}"),
            {"stage": self.stage(stage), "version": lead.version, **extra},
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_stage_changes_are_recorded(self):
        lead = self.lead()
        self.move(lead, "Консультация")
        self.move(lead, "Консультация")  # без перехода записи нет
        names = [
            (c.from_stage and c.from_stage.name, c.to_stage.name)
            for c in LeadStageChange.objects.filter(lead=lead).order_by("id")
        ]
        self.assertEqual(names, [(None, "Новое"), ("Новое", "Консультация")])

    def test_archive_records_move(self):
        lead = self.lead()
        self.post(
            self.url(f"stages/{self.stage('Новое')}/archive"),
            {"move_to": self.stage("В работе")},
        )
        last = LeadStageChange.objects.filter(lead=lead).latest("id")
        self.assertEqual(
            (last.from_stage.name, last.to_stage.name), ("Новое", "В работе")
        )

    def test_totals_sources_and_reasons(self):
        admitted = self.lead(source="Instagram")
        self.move(admitted, "Консультация")
        self.move(admitted, "Поступил")
        refused = self.lead(source="Instagram ")
        self.move(refused, "Отказ", refusal_reason="Дорого")
        self.lead()
        data = self.report().json()
        self.assertEqual(data["scope"], "company")
        self.assertEqual(
            data["totals"],
            {"created": 3, "admitted": 1, "refused": 1, "conversion": 0.3333},
        )
        sources = {row["name"]: row for row in data["sources"]}
        self.assertEqual(
            sources["Instagram"], {"name": "Instagram", "created": 2, "admitted": 1}
        )
        self.assertEqual(sources["Не указан"]["created"], 1)
        self.assertEqual(data["refusal_reasons"], [{"reason": "Дорого", "count": 1}])
        self.assertEqual(data["period"]["bucket"], "week")
        last = data["series"][-1]
        self.assertEqual((last["created"], last["admitted"]), (3, 1))

    def test_admission_counts_in_period_of_admission(self):
        old = self.lead()
        Lead.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        self.move(old, "Поступил")
        totals = self.report().json()["totals"]
        self.assertEqual((totals["created"], totals["admitted"]), (0, 1))
        self.assertIsNone(totals["conversion"])

    def test_repeated_refusal_counts_once(self):
        lead = self.lead()
        self.move(lead, "Отказ", refusal_reason="Нет")
        self.move(lead, "Новое")
        self.move(lead, "Отказ", refusal_reason="Нет")
        self.assertEqual(self.report().json()["totals"]["refused"], 1)

    def test_manager_sees_only_own_leads_and_no_team(self):
        self.lead()
        self.lead(assignee_id=str(self.owner_member.id))
        self.client.force_login(self.manager)
        data = self.report(f"?assignee={self.owner_member.id}").json()
        self.assertEqual(data["scope"], "own")
        self.assertEqual(data["totals"]["created"], 1)
        self.assertIsNone(data["team"])
        self.assertEqual(data["assignees"], [])

    def test_team_breakdown_and_filter(self):
        lead = self.lead()
        FollowUpTask.objects.create(
            lead=lead,
            title="Позвонить",
            due_at=timezone.now() - timedelta(hours=1),
            created_by=self.owner,
        )
        self.move(lead, "Поступил")
        self.lead(assignee_id=str(self.owner_member.id))
        team = {row["name"]: row for row in self.report().json()["team"]}
        self.assertEqual(
            (team["Менеджер"]["created"], team["Менеджер"]["admitted"]), (1, 1)
        )
        self.assertEqual(team["Менеджер"]["overdue_tasks"], 1)
        self.assertEqual(team["Владелец"]["overdue_tasks"], 0)
        filtered = self.report(f"?assignee={self.member.id}").json()
        self.assertEqual(filtered["totals"]["created"], 1)

    def test_foreign_company_is_hidden(self):
        url = f"/api/organizations/{self.foreign.id}/analytics/"
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_period(self):
        for query in (
            "?from=2026-02-30",
            "?from=2026-03-02&to=2026-03-01",
            "?from=2020-01-01&to=2026-01-01",
            "?tz=Mars/Base",
            "?assignee=abc",
        ):
            self.assertEqual(self.report(query).status_code, 400, query)

    def test_query_count_does_not_grow_with_leads(self):
        for _ in range(3):
            self.lead()
        with CaptureQueriesContext(connection) as small:
            self.report()
        for _ in range(6):
            self.move(self.lead(), "Поступил")
        with CaptureQueriesContext(connection) as large:
            self.report()
        self.assertEqual(len(small), len(large))

    def test_buckets(self):
        tz = ZoneInfo("Asia/Almaty")
        self.assertEqual(Period(date(2026, 3, 1), date(2026, 3, 7), tz).bucket, "day")
        weekly = Period(date(2026, 1, 1), date(2026, 3, 31), tz)
        self.assertEqual(weekly.bucket, "week")
        self.assertEqual(weekly.buckets()[0], date(2025, 12, 29))
        monthly = Period(date(2026, 1, 15), date(2026, 12, 31), tz)
        self.assertEqual(monthly.bucket, "month")
        self.assertEqual(len(monthly.buckets()), 12)
