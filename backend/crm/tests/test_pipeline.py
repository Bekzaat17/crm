from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from crm.models import Lead, LeadActivity, PipelineStage
from crm.tests.test_sales import SalesFixtures


class PipelineTests(SalesFixtures):
    def stages_url(self, tail=""):
        return self.url("stages" + (f"/{tail}" if tail else ""))

    def test_new_lead_starts_in_first_open_stage(self):
        self.assertEqual(self.lead().stage.name, "Новое")

    def test_manager_cannot_configure_pipeline(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(f"/api/{self.stages_url()}/").status_code, 403)
        response = self.post(self.stages_url(), {"name": "Звонок", "kind": "open"})
        self.assertEqual(response.status_code, 403)

    def test_custom_stage_is_used_on_board_and_in_summary(self):
        created = self.post(
            self.stages_url(),
            {"name": "Консультация прошла", "kind": "open", "color": "#AABBCC"},
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["color"], "#aabbcc")
        lead = self.lead()
        moved = self.post(
            self.url(f"leads/{lead.id}"), {"stage": created.json()["id"], "version": 1}
        )
        self.assertEqual(moved.json()["stage_label"], "Консультация прошла")
        summary = self.client.get(f"/api/{self.url('summary')}/").json()
        self.assertEqual(summary["active_leads"], 1)
        meta = self.client.get(f"/api/{self.url('pipeline')}/").json()
        self.assertIn("Консультация прошла", [s["name"] for s in meta["stages"]])

    def test_foreign_company_stage_is_rejected(self):
        lead = self.lead()
        foreign_stage = self.stage("В работе", self.foreign)
        response = self.post(
            self.url(f"leads/{lead.id}"), {"stage": foreign_stage, "version": 1}
        )
        self.assertEqual(response.status_code, 404)
        lead.refresh_from_db()
        self.assertEqual(lead.stage.name, "Новое")

    def test_archive_moves_leads_to_same_kind_with_history(self):
        lead = self.lead()
        source = self.stage("Новое")
        self.assertEqual(
            self.post(self.stages_url(f"{source}/archive"), {}).status_code, 400
        )
        wrong = self.post(
            self.stages_url(f"{source}/archive"), {"move_to": self.stage("Отказ")}
        )
        self.assertEqual(wrong.status_code, 400)
        response = self.post(
            self.stages_url(f"{source}/archive"), {"move_to": self.stage("В работе")}
        )
        self.assertEqual(response.json()["moved_leads"], 1)
        lead.refresh_from_db()
        self.assertEqual((lead.stage.name, lead.version), ("В работе", 2))
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=lead, text__contains="архивирован"
            ).exists()
        )
        moved = self.post(self.url(f"leads/{lead.id}"), {"stage": source, "version": 2})
        self.assertEqual(moved.status_code, 404)

    def test_last_stage_of_kind_cannot_be_archived(self):
        response = self.post(self.stages_url(f"{self.stage('Отказ')}/archive"), {})
        self.assertEqual(response.status_code, 409)

    def test_kind_of_stage_with_leads_is_fixed(self):
        self.lead()
        stage = PipelineStage.objects.get(organization=self.org, name="Новое")
        response = self.post(
            self.stages_url(str(stage.id)), {"kind": "refused", "version": 1}
        )
        self.assertEqual(response.status_code, 409)

    def test_reorder_requires_complete_list(self):
        ids = [
            s["id"]
            for s in self.client.get(f"/api/{self.stages_url()}/").json()["items"]
        ]
        self.assertEqual(
            self.post(self.stages_url("reorder"), {"ids": ids[:-1]}).status_code, 400
        )
        response = self.post(self.stages_url("reorder"), {"ids": list(reversed(ids))})
        self.assertEqual(response.json()["items"][0]["name"], "Отказ")

    def test_restore_rejects_duplicate_active_name(self):
        stage = self.stage("Консультация")
        self.post(self.stages_url(f"{stage}/archive"), {})
        self.post(self.stages_url(), {"name": "Консультация", "kind": "open"})
        response = self.post(self.stages_url(f"{stage}/restore"), {})
        self.assertEqual(response.status_code, 409)

    def test_refused_stage_requires_reason_for_custom_stage(self):
        created = self.post(
            self.stages_url(), {"name": "Выбрал другой центр", "kind": "refused"}
        ).json()
        lead = self.lead()
        response = self.post(
            self.url(f"leads/{lead.id}"), {"stage": created["id"], "version": 1}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Lead.objects.get(pk=lead.pk).stage.name, "Новое")


class PipelineMigrationTests(TransactionTestCase):
    """Прежние коды этапов переносятся в этапы компании (SQLite и PostgreSQL)."""

    before = [("crm", "0004_rehubcenter_admissiontransfer_deliveryattempt_and_more")]
    after = [("crm", "0006_lead_stage_fk")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_leads_keep_their_stage(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old = executor.loader.project_state(self.before).apps
        user = old.get_model("crm", "User").objects.create(
            email="migration@example.test", name="Тест", password="!"
        )
        org = old.get_model("crm", "Organization").objects.create(name="Центр")
        member = old.get_model("crm", "Membership").objects.create(
            user=user, organization=org, role="owner"
        )
        branch = old.get_model("crm", "Branch").objects.create(
            organization=org, name="Основной"
        )
        client = old.get_model("crm", "Client").objects.create(
            organization=org, created_by=user, name="Клиент"
        )
        for code in ("consultation", "refused"):
            old.get_model("crm", "Lead").objects.create(
                organization=org,
                client=client,
                assignee=member,
                branch=branch,
                title=code,
                stage=code,
                refusal_reason="Причина" if code == "refused" else "",
            )
        executor = MigrationExecutor(connection)
        executor.migrate(self.after)
        new = executor.loader.project_state(self.after).apps
        leads = new.get_model("crm", "Lead").objects.order_by("title")
        self.assertEqual(
            [(x.title, x.stage.name, x.stage.kind) for x in leads],
            [
                ("consultation", "Консультация", "open"),
                ("refused", "Отказ", "refused"),
            ],
        )
        self.assertEqual(new.get_model("crm", "PipelineStage").objects.count(), 6)
