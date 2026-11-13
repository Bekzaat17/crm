import json
import uuid
from datetime import timedelta

from django.test import Client
from django.utils import timezone

from crm.models import (
    Conversation,
    ExtensionToken,
    LeadActivity,
    Message,
)
from crm.tests.test_sales import SalesFixtures


def message(text, direction="in", **extra):
    return {"direction": direction, "author": "Собеседник", "text": text, **extra}


class ImportFixtures(SalesFixtures):
    def setUp(self):
        super().setUp()
        self.lead_record = self.lead()
        response = self.post(self.url("extension-tokens"), {"name": "Рабочий Chrome"})
        self.assertEqual(response.status_code, 201, response.content)
        self.secret = response.json()["secret"]
        self.ext = Client()  # отдельный клиент без cookie сессии

    def call(self, path, data=None, secret=None, method="post"):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {secret or self.secret}"}
        if method == "get":
            return self.ext.get(f"/api/ext/{path}/", **headers)
        return self.ext.post(
            f"/api/ext/{path}/",
            data=json.dumps(data),
            content_type="application/json",
            **headers,
        )

    def payload(self, messages, key=None, lead=None, external_id="chat-1"):
        return {
            "idempotency_key": str(key or uuid.uuid4()),
            "source": "whatsapp",
            "lead_id": str(lead or self.lead_record.id),
            "conversation": {"external_id": external_id, "title": "Тестовый диалог"},
            "messages": messages,
            "history_note": "Загружены видимые сообщения",
        }


class ConversationImportTests(ImportFixtures):
    def test_secret_is_shown_once_and_stored_hashed(self):
        token = ExtensionToken.objects.get()
        self.assertNotEqual(token.token_hash, self.secret)
        listed = self.client.get(f"/api/{self.url('extension-tokens')}/").json()
        self.assertNotIn("secret", listed["items"][0])

    def test_session_cookie_is_not_accepted(self):
        response = self.client.get("/api/ext/session/")
        self.assertEqual(response.status_code, 401)

    def test_revoked_expired_and_deactivated_tokens_are_rejected(self):
        self.assertEqual(self.call("session", method="get").status_code, 200)
        ExtensionToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.call("session", method="get").status_code, 401)
        ExtensionToken.objects.update(expires_at=timezone.now() + timedelta(days=1))
        self.owner_member.is_active = False
        self.owner_member.save()
        self.assertEqual(self.call("session", method="get").status_code, 401)
        self.owner_member.is_active = True
        self.owner_member.save()
        token = ExtensionToken.objects.get()
        self.post(self.url(f"extension-tokens/{token.id}/revoke"), {})
        self.assertEqual(self.call("session", method="get").status_code, 401)

    def test_import_is_idempotent_and_deduplicates_overlap(self):
        key = uuid.uuid4()
        first = [
            message("Здравствуйте", external_id="m1"),
            message("Да", direction="out", external_id="m2"),
        ]
        response = self.call("imports", self.payload(first, key))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["created"], 2)
        repeat = self.call("imports", self.payload(first, key))
        self.assertEqual((repeat.status_code, repeat.json()["created"]), (200, 2))
        overlap = first[1:] + [message("Спасибо", external_id="m3")]
        result = self.call("imports", self.payload(overlap)).json()
        self.assertEqual((result["created"], result["duplicates"]), (1, 1))
        self.assertEqual(Message.objects.count(), 3)
        self.assertEqual(LeadActivity.objects.filter(kind="import").count(), 2)

    def test_identical_text_without_ids_is_not_merged(self):
        response = self.call("imports", self.payload([message("ок"), message("ок")]))
        self.assertEqual(response.json()["created"], 2)

    def test_key_reused_for_other_conversation_conflicts(self):
        key = uuid.uuid4()
        self.call("imports", self.payload([message("a", external_id="x")], key))
        other = self.payload([message("b")], key, external_id="chat-2")
        self.assertEqual(self.call("imports", other).status_code, 409)

    def test_conversation_is_not_moved_to_another_lead(self):
        self.call("imports", self.payload([message("a", external_id="x")]))
        second = self.lead(title="Второе")
        response = self.call("imports", self.payload([message("b")], lead=second.id))
        self.assertEqual(response.status_code, 409)

    def test_foreign_and_invisible_leads_are_not_found(self):
        foreign_lead = self.lead_record.__class__.objects.create(
            organization=self.foreign,
            client=self.foreign_client,
            assignee=self.foreign_member,
            branch=self.foreign_branch,
            stage=self.foreign.pipeline_stages.first(),
            title="Чужое",
        )
        response = self.call(
            "imports", self.payload([message("a")], lead=foreign_lead.id)
        )
        self.assertEqual(response.status_code, 404)
        own_lead = self.lead(assignee_id=str(self.owner_member.id))
        self.client.force_login(self.manager)
        manager_secret = self.post(self.url("extension-tokens"), {}).json()["secret"]
        response = self.call(
            "imports", self.payload([message("a")], lead=own_lead.id), manager_secret
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Conversation.objects.exists())

    def test_limits_and_validation(self):
        too_many = [message(str(i)) for i in range(501)]
        self.assertEqual(self.call("imports", self.payload(too_many)).status_code, 400)
        naive = [message("a", sent_at="2026-11-13T10:00:00")]
        self.assertEqual(self.call("imports", self.payload(naive)).status_code, 400)
        huge = [message("x" * 9000) for _ in range(300)]
        self.assertEqual(self.call("imports", self.payload(huge)).status_code, 413)

    def test_conversations_on_lead_page_respect_access(self):
        self.call("imports", self.payload([message("Здравствуйте", external_id="m1")]))
        path = f"/api/{self.url(f'leads/{self.lead_record.id}/conversations')}/"
        items = self.client.get(path).json()["items"]
        self.assertEqual(items[0]["messages"][0]["text"], "Здравствуйте")
        self.client.force_login(self.foreign_member.user)
        foreign_path = f"/api/organizations/{self.foreign.id}/leads/{self.lead_record.id}/conversations/"
        self.assertEqual(self.client.get(foreign_path).status_code, 404)

    def test_telegram_source_is_accepted(self):
        data = self.payload([message("Привет", external_id="1")], external_id="@user")
        data["source"] = "telegram"
        self.assertEqual(self.call("imports", data).status_code, 201)

    def test_lead_search_for_extension(self):
        items = self.call("leads", method="get").json()["items"]
        self.assertEqual(items[0]["id"], str(self.lead_record.id))


EXT_ID = "bmpbpohmpkpikemmocmchnhccmcneolc"
REDIRECT = f"https://{EXT_ID}.chromiumapp.org/crm"


class ExtensionConnectTests(SalesFixtures):
    def authorize(self, **overrides):
        data = {
            "company_id": str(self.org.id),
            "redirect_uri": REDIRECT,
            "state": "synthetic-state-123",
            **overrides,
        }
        return self.post("extension/authorize", data)

    def test_login_flow_returns_token_in_fragment(self):
        response = self.authorize()
        self.assertEqual(response.status_code, 200, response.content)
        redirect = response.json()["redirect"]
        self.assertTrue(redirect.startswith(REDIRECT + "#"))
        params = dict(p.split("=", 1) for p in redirect.split("#", 1)[1].split("&"))
        self.assertTrue(params["token"].startswith("crx_"))
        self.assertEqual(params["state"], "synthetic-state-123")
        session = Client().get(
            "/api/ext/session/", HTTP_AUTHORIZATION=f"Bearer {params['token']}"
        )
        self.assertEqual(session.status_code, 200)

    def test_unknown_extension_and_bad_input_are_rejected(self):
        other = "https://" + "a" * 32 + ".chromiumapp.org/crm"
        self.assertEqual(self.authorize(redirect_uri=other).status_code, 403)
        self.assertEqual(
            self.authorize(redirect_uri="https://evil.example/crm").status_code, 403
        )
        self.assertEqual(self.authorize(state="x").status_code, 400)
        self.client.force_login(self.manager)
        foreign = self.authorize(company_id=str(self.foreign.id))
        self.assertEqual(foreign.status_code, 404)
        self.assertFalse(ExtensionToken.objects.exists())

    def test_requires_session(self):
        self.client.logout()
        self.assertEqual(self.authorize().status_code, 401)


class TrackingTests(ImportFixtures):
    def chat(self, **extra):
        return {"source": "whatsapp", "external_id": "77000000000@c.us", **extra}

    def test_track_lookup_untrack(self):
        lookup = self.ext.get(
            "/api/ext/conversations/lookup/",
            self.chat(),
            HTTP_AUTHORIZATION=f"Bearer {self.secret}",
        ).json()
        self.assertFalse(lookup["tracked"])
        tracked = self.call(
            "conversations/track",
            self.chat(title="Тестовый чат", lead_id=str(self.lead_record.id)),
        ).json()
        self.assertTrue(tracked["tracked"])
        self.assertEqual(tracked["lead"]["id"], str(self.lead_record.id))
        again = self.ext.get(
            "/api/ext/conversations/lookup/",
            self.chat(),
            HTTP_AUTHORIZATION=f"Bearer {self.secret}",
        ).json()
        self.assertTrue(again["tracked"])
        self.assertFalse(
            self.call("conversations/untrack", self.chat()).json()["tracked"]
        )

    def test_tracked_chat_with_messages_is_not_moved(self):
        self.call(
            "imports",
            self.payload(
                [message("a", external_id="1")], external_id="77000000000@c.us"
            ),
        )
        other = self.lead(title="Второе")
        response = self.call(
            "conversations/track",
            self.chat(title="Чат", lead_id=str(other.id)),
        )
        self.assertEqual(response.status_code, 409)

    def test_match_by_normalized_phone(self):
        # У клиента номер +70000000000, в мессенджере тот же номер без «+».
        self.client_record.phone_digits = "70000000000"
        self.client_record.save()
        found = self.call("match", method="get")
        self.assertEqual(found.status_code, 200)
        response = self.ext.get(
            "/api/ext/match/",
            {"phone": "8 (000) 000-00-00"},
            HTTP_AUTHORIZATION=f"Bearer {self.secret}",
        ).json()
        self.assertEqual(
            [i["id"] for i in response["items"]], [str(self.lead_record.id)]
        )

    def test_client_phone_digits_are_saved(self):
        self.post(
            self.url(f"clients/{self.client_record.id}"),
            {"name": "Тестовый клиент", "phone": "8 701 000-00-01", "version": 1},
        )
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.phone_digits, "77010000001")
