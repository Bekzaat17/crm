import json

from django.test import TestCase

from crm.models import (
    Branch,
    Client,
    Lead,
    LeadActivity,
    Membership,
    Organization,
    User,
)
from crm.sales import services
from crm.services import ApiError


class SalesFixtures(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@sales.test", name="Владелец", password="Sales-River-5748!"
        )
        self.org = Organization.objects.create(name="Первый центр")
        self.owner_member = Membership.objects.create(
            user=self.owner, organization=self.org, role="owner"
        )
        self.branch = Branch.objects.create(organization=self.org, name="Основной")
        self.manager = User.objects.create_user(
            email="manager@sales.test", name="Менеджер", password="Sales-River-5748!"
        )
        self.member = Membership.objects.create(
            user=self.manager, organization=self.org, role="manager"
        )
        self.foreign = Organization.objects.create(name="Другой центр")
        self.foreign_branch = Branch.objects.create(
            organization=self.foreign, name="Другой"
        )
        self.foreign_member = Membership.objects.create(
            user=self.owner, organization=self.foreign, role="owner"
        )
        self.client_record = services.create_client(
            self.owner,
            self.org.id,
            {"name": "Тестовый клиент", "phone": "+70000000000"},
        )
        self.foreign_client = services.create_client(
            self.owner, self.foreign.id, {"name": "Чужой клиент"}
        )
        self.client.force_login(self.owner)

    def post(self, path, data):
        return self.client.post(
            "/api/" + path + "/", data=json.dumps(data), content_type="application/json"
        )

    def url(self, tail):
        return f"organizations/{self.org.id}/{tail}"

    def lead(self, **values):
        data = dict(
            client_id=str(self.client_record.id),
            assignee_id=str(self.member.id),
            branch_id=str(self.branch.id),
            title="Консультация",
        )
        data.update(values)
        return services.create_lead(self.owner, self.org.id, data)


class SalesTests(SalesFixtures):
    def test_create_and_search_client_without_merging_phone(self):
        response = self.post(
            self.url("clients"), {"name": "Второй клиент", "phone": "+70000000000"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Client.objects.filter(organization=self.org).count(), 2)
        result = self.client.get("/api/" + self.url("clients") + "/?q=7000").json()
        self.assertEqual(result["total"], 2)

    def test_client_update_requires_current_version(self):
        path = self.url(f"clients/{self.client_record.id}")
        self.assertEqual(
            self.post(path, {"name": "Новое имя", "version": 1}).status_code, 200
        )
        self.assertEqual(
            self.post(path, {"name": "Старое изменение", "version": 1}).status_code, 409
        )
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.name, "Новое имя")

    def test_client_birthday_validation(self):
        for value in ("3000-01-01", "bad", [], "2024-99-99"):
            self.assertEqual(
                self.post(
                    self.url("clients"), {"name": "Клиент", "date_of_birth": value}
                ).status_code,
                400,
            )

    def test_manager_sees_only_assigned_clients_and_leads(self):
        own = self.lead()
        hidden = self.lead(assignee_id=str(self.owner_member.id))
        self.client.force_login(self.manager)
        result = self.client.get("/api/" + self.url("leads") + "/").json()
        self.assertEqual([x["id"] for x in result["items"]], [str(own.id)])
        self.assertEqual(
            self.client.get("/api/" + self.url(f"leads/{hidden.id}") + "/").status_code,
            404,
        )
        card = self.client.get(
            "/api/" + self.url(f"clients/{self.client_record.id}") + "/"
        ).json()
        self.assertEqual([x["id"] for x in card["leads"]], [str(own.id)])

    def test_manager_cannot_read_unassigned_client(self):
        self.client.force_login(self.manager)
        self.assertEqual(
            self.client.get(
                "/api/" + self.url(f"clients/{self.client_record.id}") + "/"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.post(
                self.url(f"clients/{self.client_record.id}/contacts"),
                {"name": "Имя", "relationship": "Мать"},
            ).status_code,
            404,
        )

    def test_manager_can_create_own_client_and_lead(self):
        self.client.force_login(self.manager)
        c = self.post(self.url("clients"), {"name": "Новый клиент"}).json()
        response = self.post(
            self.url("leads"),
            dict(client_id=c["id"], branch_id=str(self.branch.id), title="Звонок"),
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["assignee_id"], str(self.member.id))

    def test_manager_cannot_assign_to_other_employee(self):
        c = services.create_client(
            self.manager, self.org.id, {"name": "Клиент менеджера"}
        )
        self.client.force_login(self.manager)
        response = self.post(
            self.url("leads"),
            dict(
                client_id=str(c.id),
                branch_id=str(self.branch.id),
                assignee_id=str(self.owner_member.id),
                title="Звонок",
            ),
        )
        self.assertEqual(response.status_code, 403)

    def test_reassignment_removes_old_manager_access(self):
        lead = self.lead()
        services.update_lead(
            self.owner,
            self.org.id,
            lead.id,
            {"assignee_id": str(self.owner_member.id), "version": 1},
        )
        self.client.force_login(self.manager)
        self.assertEqual(
            self.client.get("/api/" + self.url(f"leads/{lead.id}") + "/").status_code,
            404,
        )
        self.assertEqual(
            self.post(
                self.url(f"leads/{lead.id}/comments"), {"text": "Текст"}
            ).status_code,
            404,
        )

    def test_reject_foreign_client_assignee_and_branch(self):
        for values in (
            {"client_id": str(self.foreign_client.id)},
            {"assignee_id": str(self.foreign_member.id)},
            {"branch_id": str(self.foreign_branch.id)},
        ):
            with self.assertRaises(ApiError):
                self.lead(**values)
        self.assertFalse(Lead.objects.exists())

    def test_invalid_uuid_returns_json_error(self):
        self.assertEqual(
            self.post(
                self.url("leads"), dict(client_id="bad", title="Тест")
            ).status_code,
            400,
        )

    def test_inactive_assignee_rejected(self):
        self.member.is_active = False
        self.member.save()
        with self.assertRaises(ApiError):
            self.lead()

    def test_refusal_requires_reason_and_logs_change(self):
        lead = self.lead()
        path = self.url(f"leads/{lead.id}")
        self.assertEqual(
            self.post(path, {"stage": "refused", "version": 1}).status_code, 400
        )
        response = self.post(
            path,
            {"stage": "refused", "refusal_reason": "Отложил решение", "version": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["refusal_reason"], "Отложил решение")
        self.assertIn("Отказ", response.json()["activities"][0]["text"])
        self.assertEqual(
            self.post(path, {"stage": "work", "version": 1}).status_code, 409
        )
        self.assertEqual(
            self.post(path, {"stage": "work", "version": 2}).json()["refusal_reason"],
            "",
        )

    def test_comment_and_contact_are_stored_separately(self):
        lead = self.lead()
        self.assertEqual(
            self.post(
                self.url(f"leads/{lead.id}/comments"), {"text": "Перезвонить завтра"}
            ).status_code,
            201,
        )
        self.assertEqual(
            self.post(
                self.url(f"clients/{self.client_record.id}/contacts"),
                {
                    "name": "Родственник",
                    "relationship": "Брат",
                    "phone": "+70000000000",
                },
            ).status_code,
            201,
        )
        self.assertEqual(self.client_record.contacts.count(), 1)
        self.assertEqual(
            LeadActivity.objects.filter(lead=lead, kind="comment").count(), 1
        )

    def test_foreign_company_endpoints_are_inaccessible_to_manager(self):
        self.client.force_login(self.manager)
        for endpoint in ("clients", "leads", "pipeline"):
            self.assertEqual(
                self.client.get(
                    f"/api/organizations/{self.foreign.id}/{endpoint}/"
                ).status_code,
                404,
            )

    def test_next_contact_requires_timezone(self):
        lead = self.lead()
        path = self.url(f"leads/{lead.id}")
        self.assertEqual(
            self.post(
                path, {"next_contact_at": "2026-11-14T12:30", "version": 1}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                path, {"next_contact_at": "2026-11-14T12:30:00+05:00", "version": 1}
            ).status_code,
            200,
        )

    def test_list_pagination_and_stage_counts(self):
        leads = [
            Lead(
                organization=self.org,
                client=self.client_record,
                assignee=self.member,
                branch=self.branch,
                title=f"Звонок {i}",
            )
            for i in range(52)
        ]
        Lead.objects.bulk_create(leads)
        first = self.client.get("/api/" + self.url("leads") + "/").json()
        second = self.client.get("/api/" + self.url("leads") + "/?page=2").json()
        self.assertEqual(first["total"], 52)
        self.assertEqual(first["counts"]["new"], 52)
        self.assertEqual(len(first["items"]), 50)
        self.assertEqual(len(second["items"]), 2)
        self.assertFalse(second["has_more"])

    def test_unchanged_fields_do_not_clutter_history(self):
        lead = self.lead()
        services.update_lead(
            self.owner,
            self.org.id,
            lead.id,
            {
                "title": lead.title,
                "source": lead.source,
                "next_contact_at": "",
                "version": lead.version,
            },
        )
        self.assertEqual(LeadActivity.objects.filter(lead=lead).count(), 1)
