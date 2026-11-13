"""Регрессии по итогам ревью: безопасность, целостность и число запросов."""

import json
from datetime import timedelta

from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from crm.accounts.services import reset_password
from crm.core.throttle import client_ip
from crm.models import (
    Conversation,
    ExtensionToken,
    FollowUpTask,
    Invitation,
    Lead,
    LeadActivity,
    Membership,
    PipelineStage,
    ReminderDispatch,
    User,
)
from crm.notifications.reminders import schedule_reminders
from crm.organizations.services import invite_owner
from crm.tests.test_sales import SalesFixtures

PASSWORD = "Sales-River-5748!"


class ReviewFixesTests(SalesFixtures):
    def ext(self, user=None):
        self.client.force_login(user or self.owner)
        secret = self.post(self.url("extension-tokens"), {}).json()["secret"]
        return secret

    def ext_post(self, secret, path, data):
        return Client().post(
            f"/api/ext/{path}/",
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {secret}",
        )

    def test_deactivation_and_password_reset_revoke_extension_keys(self):
        secret = self.ext(self.manager)
        self.client.force_login(self.owner)
        self.post(self.url(f"members/{self.member.id}/deactivate"), {})
        self.member.is_active = True  # повторное подключение не оживляет ключ
        self.member.save()
        self.assertEqual(self.ext_post(secret, "session", {}).status_code, 405)
        session = Client().get(
            "/api/ext/session/", HTTP_AUTHORIZATION=f"Bearer {secret}"
        )
        self.assertEqual(session.status_code, 401)
        owner_secret = self.ext()
        from django.contrib.auth.tokens import default_token_generator

        reset_password(
            {
                "uid": str(self.owner.id),
                "token": default_token_generator.make_token(self.owner),
                "password": "Copper-Meadow-8274!",
            }
        )
        session = Client().get(
            "/api/ext/session/", HTTP_AUTHORIZATION=f"Bearer {owner_secret}"
        )
        self.assertEqual(session.status_code, 401)

    def test_new_owner_invitation_revokes_previous_one(self):
        admin = User.objects.create_superuser(
            email="platform@sales.test", password=PASSWORD, name="Платформа"
        )
        Membership.objects.filter(organization=self.foreign).delete()
        first = invite_owner(admin, self.foreign, "typo@sales.test")
        invite_owner(admin, self.foreign, "right@sales.test")
        first.refresh_from_db()
        self.assertIsNotNone(first.revoked_at)
        pending = Invitation.objects.filter(
            organization=self.foreign, revoked_at__isnull=True
        )
        self.assertEqual([i.email for i in pending], ["right@sales.test"])

    def test_client_ip_trusts_forwarded_only_from_proxy(self):
        factory = RequestFactory()
        proxied = factory.get(
            "/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="1.1.1.1, 2.2.2.2"
        )
        self.assertEqual(client_ip(proxied), "2.2.2.2")
        direct = factory.get("/", REMOTE_ADDR="8.8.8.8", HTTP_X_FORWARDED_FOR="1.1.1.1")
        self.assertEqual(client_ip(direct), "8.8.8.8")

    def test_track_cannot_take_over_invisible_conversation(self):
        own_lead = self.lead(assignee_id=str(self.owner_member.id))
        Conversation.objects.create(
            organization=self.org,
            source="whatsapp",
            external_id="77000000001@c.us",
            title="Чат",
            lead=own_lead,
            created_by=self.owner,
        )
        manager_secret = self.ext(self.manager)
        manager_lead = self.lead()
        response = self.ext_post(
            manager_secret,
            "conversations/track",
            {
                "source": "whatsapp",
                "external_id": "77000000001@c.us",
                "title": "Чат",
                "lead_id": str(manager_lead.id),
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Conversation.objects.get().lead_id, own_lead.id)

    def test_admin_cannot_revoke_admin_invitation(self):
        self.post(self.url("invitations"), {"email": "a2@sales.test", "role": "admin"})
        admin = User.objects.create_user(
            email="admin@sales.test", password=PASSWORD, name="Админ"
        )
        Membership.objects.create(user=admin, organization=self.org, role="admin")
        self.client.force_login(admin)
        invitation = Invitation.objects.get(email="a2@sales.test")
        response = self.post(self.url(f"invitations/{invitation.id}/revoke"), {})
        self.assertEqual(response.status_code, 403)

    def test_deeply_nested_json_is_rejected(self):
        response = self.client.post(
            "/api/" + self.url("clients") + "/",
            data="[" * 5000,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_contact_change_invalidates_admission_preview(self):
        version = self.client_record.version
        self.post(
            self.url(f"clients/{self.client_record.id}/contacts"),
            {"name": "Мать", "relationship": "Мать"},
        )
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.version, version + 1)

    def test_stage_names_are_unique_case_insensitive(self):
        response = self.post(self.url("stages"), {"name": "новое", "kind": "open"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("названием", response.json()["error"])

    def test_phone_search_ignores_format(self):
        self.post(
            self.url(f"clients/{self.client_record.id}"),
            {"name": "Тестовый клиент", "phone": "+7 701 000-00-01", "version": 1},
        )
        found = self.client.get(
            "/api/" + self.url("clients") + "/?q=" + "87010000001"
        ).json()
        self.assertEqual(found["total"], 1)

    def test_archived_stage_moves_leads_to_top_of_board(self):
        lead = self.lead()
        Lead.objects.filter(pk=lead.pk).update(
            updated_at=timezone.now() - timedelta(days=3)
        )
        stage = PipelineStage.objects.get(organization=self.org, name="Новое")
        self.post(
            self.url(f"stages/{stage.id}/archive"),
            {"move_to": self.stage("В работе")},
        )
        lead.refresh_from_db()
        self.assertGreater(lead.updated_at, timezone.now() - timedelta(minutes=1))

    def test_reassigned_lead_reminds_new_assignee(self):
        lead = self.lead()
        due = timezone.now() - timedelta(minutes=5)
        FollowUpTask.objects.create(
            lead=lead, title="Позвонить", due_at=due, created_by=self.owner
        )
        self.assertEqual(schedule_reminders(), 1)
        Lead.objects.filter(pk=lead.pk).update(assignee=self.owner_member)
        self.assertEqual(schedule_reminders(), 1)
        self.assertEqual(
            set(ReminderDispatch.objects.values_list("user__email", flat=True)),
            {"manager@sales.test", "owner@sales.test"},
        )

    def test_extension_logout_revokes_key_and_empty_import_is_quiet(self):
        secret = self.ext()
        lead = self.lead()
        payload = {
            "idempotency_key": "11111111-1111-1111-1111-111111111111",
            "source": "telegram",
            "lead_id": str(lead.id),
            "conversation": {"external_id": "123", "title": "Чат"},
            "messages": [{"direction": "in", "author": "", "text": "Привет"}],
        }
        self.ext_post(secret, "imports", payload)
        payload["idempotency_key"] = "22222222-2222-2222-2222-222222222222"
        self.ext_post(secret, "imports", payload)
        self.assertEqual(
            LeadActivity.objects.filter(lead=lead, kind="import").count(), 1
        )
        self.assertEqual(self.ext_post(secret, "session/revoke", {}).status_code, 200)
        self.assertIsNotNone(ExtensionToken.objects.get().revoked_at)


class QueryCountTests(SalesFixtures):
    """Число запросов списка не растёт с числом записей (нет N+1)."""

    def queries(self, path):
        with CaptureQueriesContext(connection) as context:
            self.assertEqual(self.client.get(path).status_code, 200)
        return len(context)

    def test_lead_list_and_platform_companies(self):
        self.lead()
        leads_path = "/api/" + self.url("leads") + "/"
        one = self.queries(leads_path)
        for i in range(5):
            self.lead(title=f"Ещё {i}")
        self.assertEqual(self.queries(leads_path), one)

        admin = User.objects.create_superuser(
            email="platform@sales.test", password=PASSWORD, name="Платформа"
        )
        self.client.force_login(admin)
        companies_path = "/api/platform/companies/"
        before = self.queries(companies_path)
        for i in range(4):
            self.post("platform/companies", {"name": f"Центр {i}"})
        self.assertEqual(self.queries(companies_path), before)

    def test_conversations_on_lead_page(self):
        lead = self.lead()
        path = "/api/" + self.url(f"leads/{lead.id}/conversations") + "/"
        base = self.queries(path)
        self.assertLessEqual(base, 6)
