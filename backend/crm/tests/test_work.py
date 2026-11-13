from datetime import timedelta

from django.utils import timezone

from crm.models import FollowUpTask, LeadActivity
from crm.sales import services as sales
from crm.tests.test_sales import SalesFixtures
from crm.work import services


class WorkTests(SalesFixtures):
    def task(self, lead=None):
        return services.create_task(
            self.owner,
            self.org.id,
            (lead or self.lead()).id,
            {
                "title": "Перезвонить",
                "due_at": (timezone.now() - timedelta(hours=1)).isoformat(),
            },
        )

    def test_create_task_is_atomic_and_records_activity(self):
        lead = self.lead()
        response = self.post(
            self.url(f"leads/{lead.id}/tasks"),
            {
                "title": "Назначить консультацию",
                "due_at": timezone.now().isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["assignee_name"], self.manager.name)
        self.assertTrue(LeadActivity.objects.filter(lead=lead, kind="task").exists())

    def test_invalid_deadline_does_not_create_task(self):
        lead = self.lead()
        for due in ("bad", "2026-11-13T10:00", [], "2026-99-99"):
            response = self.post(
                self.url(f"leads/{lead.id}/tasks"), {"title": "Задача", "due_at": due}
            )
            self.assertEqual(response.status_code, 400)
        self.assertFalse(FollowUpTask.objects.exists())

    def test_complete_and_reopen_with_optimistic_lock(self):
        task = self.task()
        path = self.url(f"tasks/{task.id}")
        self.assertTrue(
            self.post(path, {"completed": True, "version": 1}).json()["completed"]
        )
        self.assertEqual(
            self.post(path, {"completed": False, "version": 1}).status_code, 409
        )
        self.assertFalse(
            self.post(path, {"completed": False, "version": 2}).json()["completed"]
        )
        self.assertEqual(
            self.post(path, {"completed": "false", "version": 3}).status_code, 400
        )

    def test_move_deadline_removes_overdue_reminder(self):
        task = self.task()
        self.assertEqual(
            self.client.get("/api/" + self.url("tasks") + "/?status=overdue").json()[
                "total"
            ],
            1,
        )
        self.post(
            self.url(f"tasks/{task.id}"),
            {"due_at": (timezone.now() + timedelta(days=2)).isoformat(), "version": 1},
        )
        self.assertEqual(
            self.client.get("/api/" + self.url("tasks") + "/?status=overdue").json()[
                "total"
            ],
            0,
        )

    def test_manager_cannot_read_or_change_another_assignees_tasks(self):
        task = self.task(self.lead(assignee_id=str(self.owner_member.id)))
        self.client.force_login(self.manager)
        self.assertEqual(
            self.client.get("/api/" + self.url("tasks") + "/").json()["total"], 0
        )
        self.assertEqual(
            self.post(
                self.url(f"tasks/{task.id}"), {"version": 1, "completed": True}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.post(
                self.url(f"leads/{task.lead_id}/tasks"),
                {"title": "Скрытая", "due_at": timezone.now().isoformat()},
            ).status_code,
            404,
        )

    def test_reassignment_moves_tasks_with_lead(self):
        task = self.task()
        sales.update_lead(
            self.owner,
            self.org.id,
            task.lead_id,
            {"version": 1, "assignee_id": str(self.owner_member.id)},
        )
        self.client.force_login(self.manager)
        self.assertEqual(
            self.client.get("/api/" + self.url("tasks") + "/").json()["total"], 0
        )

    def test_foreign_company_endpoints_are_hidden(self):
        self.client.force_login(self.manager)
        for endpoint in ("tasks", "summary", "contacts-due"):
            self.assertEqual(
                self.client.get(
                    f"/api/organizations/{self.foreign.id}/{endpoint}/"
                ).status_code,
                404,
            )

    def test_summary_and_due_contacts_obey_visibility(self):
        lead = self.lead()
        self.task(lead)
        sales.update_lead(
            self.owner,
            self.org.id,
            lead.id,
            {
                "version": 1,
                "next_contact_at": (timezone.now() - timedelta(hours=1)).isoformat(),
            },
        )
        self.client.force_login(self.manager)
        data = self.client.get("/api/" + self.url("summary") + "/").json()
        self.assertEqual(data["leads"], 1)
        self.assertEqual(data["overdue_tasks"], 1)
        self.assertEqual(data["contacts_due"], 1)
        for _ in range(2):
            self.assertEqual(
                self.client.get("/api/" + self.url("contacts-due") + "/").json()[
                    "total"
                ],
                1,
            )
        self.assertEqual(FollowUpTask.objects.count(), 1)

    def test_closed_lead_is_not_a_due_contact(self):
        lead = self.lead()
        sales.update_lead(
            self.owner,
            self.org.id,
            lead.id,
            {
                "version": 1,
                "next_contact_at": (timezone.now() - timedelta(hours=1)).isoformat(),
                "stage": "admitted",
            },
        )
        self.assertEqual(
            self.client.get("/api/" + self.url("contacts-due") + "/").json()["total"], 0
        )

    def test_unsupported_filter_is_rejected(self):
        self.assertEqual(
            self.client.get(
                "/api/" + self.url("tasks") + "/?status=unknown"
            ).status_code,
            400,
        )
