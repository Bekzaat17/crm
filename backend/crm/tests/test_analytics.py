from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from crm.analytics.period import Period
from crm.models import Lead, LeadStageChange, PipelineStage
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

    def test_totals_funnel_and_sources(self):
        admitted = self.lead(source="Instagram")
        self.move(admitted, "Консультация")
        self.move(admitted, "Поступил")
        refused = self.lead(source="instagram ")
        self.move(refused, "В работе")
        self.move(refused, "Отказ", refusal_reason="Дорого")
        self.lead()
        data = self.report().json()
        self.assertEqual(data["scope"], "company")
        totals = data["totals"]
        self.assertEqual(
            (totals["created"], totals["open"], totals["admitted"], totals["refused"]),
            (3, 1, 1, 1),
        )
        self.assertAlmostEqual(totals["conversion"], 1 / 3, places=3)
        self.assertEqual(totals["median_days_to_admission"], 0.0)
        funnel = {step["name"]: step["count"] for step in data["funnel"]}
        self.assertEqual(
            funnel,
            {
                "Новое": 3,
                "В работе": 2,
                "Консультация": 1,
                "Ожидаем поступление": 1,
                "Поступили": 1,
            },
        )
        sources = {row["name"]: row for row in data["sources"]}
        self.assertEqual(sources["Instagram"]["admitted"], 1)
        self.assertEqual(sources["Не указан"]["created"], 1)
        self.assertEqual(data["refusal_reasons"], [{"reason": "Дорого", "count": 1}])
        series = data["series"]
        self.assertEqual(data["period"]["bucket"], "day")
        self.assertEqual(len(series), 30)
        today = series[-1]
        self.assertEqual(
            (today["created"], today["admitted"], today["refused"]), (3, 1, 1)
        )

    def test_period_excludes_older_leads_and_compares_previous(self):
        old = self.lead()
        Lead.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        self.lead()
        data = self.report().json()
        self.assertEqual(data["totals"]["created"], 1)
        self.assertEqual(data["previous"]["created"], 1)

    def test_manager_sees_only_own_leads_and_no_team(self):
        self.lead()
        self.lead(assignee_id=str(self.owner_member.id))
        self.client.force_login(self.manager)
        data = self.report(f"?assignee={self.owner_member.id}").json()
        self.assertEqual(data["scope"], "own")
        self.assertEqual(data["totals"]["created"], 1)
        self.assertIsNone(data["team"])
        self.assertEqual(data["filters"]["assignees"], [])

    def test_team_breakdown_and_filters(self):
        lead = self.lead()
        FollowUpTask.objects.create(
            lead=lead,
            title="Позвонить",
            due_at=timezone.now() - timedelta(hours=1),
            created_by=self.owner,
        )
        self.lead(assignee_id=str(self.owner_member.id))
        team = {row["name"]: row for row in self.report().json()["team"]}
        self.assertEqual(team["Менеджер"]["created"], 1)
        self.assertEqual(team["Менеджер"]["overdue_tasks"], 1)
        self.assertEqual(team["Владелец"]["overdue_tasks"], 0)
        filtered = self.report(f"?assignee={self.member.id}").json()
        self.assertEqual(filtered["totals"]["created"], 1)
        other_branch = self.report(f"?branch={self.foreign_branch.id}").json()
        self.assertEqual(other_branch["totals"]["created"], 0)

    def test_foreign_company_is_hidden(self):
        url = f"/api/organizations/{self.foreign.id}/analytics/"
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_period(self):
        self.assertEqual(self.report("?from=2026-02-30").status_code, 400)
        self.assertEqual(self.report("?from=2026-03-02&to=2026-03-01").status_code, 400)
        self.assertEqual(self.report("?from=2020-01-01&to=2026-01-01").status_code, 400)
        self.assertEqual(self.report("?tz=Mars/Base").status_code, 400)
        self.assertEqual(self.report("?branch=abc").status_code, 400)

    def test_query_count_does_not_grow_with_leads(self):
        for _ in range(3):
            self.lead()
        with CaptureQueriesContext(connection) as small:
            self.report()
        for _ in range(6):
            self.move(self.lead(), "В работе")
        with CaptureQueriesContext(connection) as large:
            self.report()
        self.assertEqual(len(small), len(large))

    def test_buckets(self):
        tz = ZoneInfo("Asia/Almaty")
        weekly = Period(date(2026, 1, 1), date(2026, 3, 1), tz)
        self.assertEqual(weekly.bucket, "week")
        self.assertEqual(weekly.buckets()[0], date(2025, 12, 29))
        monthly = Period(date(2026, 1, 15), date(2026, 12, 31), tz)
        self.assertEqual(monthly.bucket, "month")
        self.assertEqual(len(monthly.buckets()), 12)
        self.assertEqual(Period(date(2026, 3, 1), date(2026, 3, 31), tz).bucket, "day")


class StageKindTests(SalesFixtures):
    def test_reopened_refusal_is_not_counted_twice(self):
        lead = self.lead()
        lead.refresh_from_db()
        self.post(
            self.url(f"leads/{lead.id}"),
            {"stage": self.stage("Отказ"), "refusal_reason": "Нет", "version": 1},
        )
        self.post(
            self.url(f"leads/{lead.id}"), {"stage": self.stage("Новое"), "version": 2}
        )
        self.post(
            self.url(f"leads/{lead.id}"),
            {"stage": self.stage("Отказ"), "refusal_reason": "Нет", "version": 3},
        )
        data = self.client.get(f"/api/{self.url('analytics')}/").json()
        # Каждый отказ — событие динамики; итог когорты — по текущему этапу.
        self.assertEqual(sum(row["refused"] for row in data["series"]), 2)
        self.assertEqual(data["totals"]["refused"], 1)
        self.assertEqual(
            PipelineStage.objects.get(pk=self.stage("Отказ")).kind, "refused"
        )
