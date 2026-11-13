import json
import re
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from crm.core.tokens import digest
from crm.models import (
    Invitation,
    Membership,
    Organization,
    User,
)
from crm.notifications.dispatch import dispatch_all
from crm.notifications.models import OutboundMessage

PASSWORD = "Saffron-River-4729!"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountHelpers(TestCase):
    def post(self, path, data, client=None):
        return (client or self.client).post(
            f"/api/{path}/", data=json.dumps(data), content_type="application/json"
        )

    def mail_params(self):
        # Письма уходят через очередь: отправляем всё готовое перед чтением.
        dispatch_all()
        url = re.search(r"http[^\s]+", mail.outbox[-1].body).group(0)
        return parse_qs(urlparse(url).fragment)

    def owner(self, email="owner@example.test", company="Первый центр"):
        user = User.objects.create_user(email=email, password=PASSWORD, name="Владелец")
        org = Organization.objects.create(name=company)
        Membership.objects.create(user=user, organization=org, role="owner")
        self.client.force_login(user)
        return user, org

    def invitation(self, org, email="manager@example.test", role="manager"):
        response = self.post(
            f"organizations/{org.id}/invitations", {"email": email, "role": role}
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["id"], self.mail_params()["token"][0]


class AccountTests(AccountHelpers):
    def test_database_rejects_case_insensitive_duplicate_email(self):
        self.owner()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email="OWNER@EXAMPLE.TEST", name="Другой")

    def test_login_normalizes_email_and_logout_closes_session(self):
        self.owner()
        self.client.logout()
        response = self.post(
            "auth/login", {"email": "OWNER@EXAMPLE.TEST", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["organizations"]), 1)
        self.assertEqual(self.post("auth/logout", {}).status_code, 200)
        self.assertIsNone(self.client.get("/api/auth/session/").json()["user"])

    def test_login_rate_limit(self):
        for _ in range(10):
            self.assertEqual(
                self.post(
                    "auth/login",
                    {"email": "missing@example.test", "password": PASSWORD},
                ).status_code,
                401,
            )
        self.assertEqual(
            self.post(
                "auth/login", {"email": "missing@example.test", "password": PASSWORD}
            ).status_code,
            429,
        )

    def test_csrf_is_required_even_for_login(self):
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post("auth/login", {}, browser).status_code, 403)
        response = browser.get("/api/auth/session/")
        self.assertIn("csrf_token", response.json())
        response = browser.post(
            "/api/auth/login/",
            data=json.dumps({"email": "csrf@example.test", "password": PASSWORD}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=response.json()["csrf_token"],
        )
        self.assertEqual(response.status_code, 401)

    def test_invitation_creates_employee_without_extra_company(self):
        _, org = self.owner()
        invitation_id, token = self.invitation(org)
        invite = Invitation.objects.get(pk=invitation_id)
        self.assertNotEqual(invite.token_hash, token)
        self.client.logout()
        response = self.post(
            "invitations/accept",
            {"token": token, "name": "Менеджер", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(
            Membership.objects.get(user__email="manager@example.test").role, "manager"
        )
        self.assertEqual(
            self.post("invitations/accept", {"token": token}).status_code, 404
        )

    def test_existing_account_must_authenticate_before_accepting(self):
        _, org = self.owner()
        user = User.objects.create_user(
            email="existing@example.test", password=PASSWORD, name="Сотрудник"
        )
        _, token = self.invitation(org, user.email)
        self.client.logout()
        self.assertEqual(
            self.post(
                "invitations/accept",
                {"token": token, "name": "Подмена", "password": PASSWORD},
            ).status_code,
            409,
        )
        self.client.force_login(user)
        self.assertEqual(
            self.post("invitations/accept", {"token": token}).status_code, 200
        )

    def test_wrong_signed_in_user_cannot_accept(self):
        _, org = self.owner()
        _, token = self.invitation(org)
        self.assertEqual(
            self.post("invitations/accept", {"token": token}).status_code, 403
        )
        self.assertIsNone(Invitation.objects.get().accepted_at)

    def test_expired_invite_cannot_be_accepted(self):
        _, org = self.owner()
        _, token = self.invitation(org)
        Invitation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.client.logout()
        self.assertEqual(
            self.post(
                "invitations/accept",
                {"token": token, "name": "Имя", "password": PASSWORD},
            ).status_code,
            404,
        )

    def test_revoked_invite_cannot_be_accepted(self):
        _, org = self.owner()
        invitation_id, token = self.invitation(org)
        self.assertEqual(
            self.post(
                f"organizations/{org.id}/invitations/{invitation_id}/revoke", {}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post("invitations/preview", {"token": token}).status_code, 404
        )

    def test_inviting_owner_is_forbidden(self):
        _, org = self.owner()
        response = self.post(
            f"organizations/{org.id}/invitations",
            {"email": "bad@example.test", "role": "owner"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Invitation.objects.exists())

    def test_duplicate_invitation_is_rejected(self):
        _, org = self.owner()
        self.invitation(org)
        response = self.post(
            f"organizations/{org.id}/invitations",
            {"email": "MANAGER@EXAMPLE.TEST", "role": "admin"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Invitation.objects.count(), 1)

    def test_mail_failure_keeps_invitation_and_retries(self):
        _, org = self.owner()
        response = self.post(
            f"organizations/{org.id}/invitations",
            {"email": "manager@example.test", "role": "manager"},
        )
        self.assertEqual(response.status_code, 201)
        message = OutboundMessage.objects.get(kind="invite")
        self.assertNotIn("token=", message.body)  # тело зашифровано
        with patch("crm.notifications.channels.send_mail", side_effect=OSError("down")):
            dispatch_all()
        message.refresh_from_db()
        self.assertEqual(
            (message.status, message.last_error), ("retry", "smtp_unavailable")
        )
        self.assertTrue(Invitation.objects.exists())
        OutboundMessage.objects.update(next_attempt_at=timezone.now())
        dispatch_all()
        message.refresh_from_db()
        self.assertEqual(message.status, "sent")
        self.assertEqual((message.subject, message.body), ("", ""))
        self.assertIn("token=", mail.outbox[-1].body)

    def test_password_reset_is_single_use_and_invalidates_existing_sessions(self):
        user, org = self.owner()
        another_session = Client()
        another_session.force_login(user)
        self.assertEqual(
            self.post("auth/forgot", {"email": user.email}).status_code, 202
        )
        params = {key: value[0] for key, value in self.mail_params().items()}
        params["password"] = "Cedar-Mountain-6947!"
        self.assertEqual(self.post("auth/reset", params).status_code, 200)
        self.assertEqual(self.post("auth/reset", params).status_code, 400)
        self.assertEqual(
            another_session.get(f"/api/organizations/{org.id}/").status_code, 401
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password(params["password"]))

    def test_missing_reset_account_has_same_response(self):
        user, _ = self.owner()
        a = self.post("auth/forgot", {"email": user.email})
        b = self.post("auth/forgot", {"email": "unknown@example.test"})
        self.assertEqual(a.json(), b.json())

    def test_json_and_methods_are_validated(self):
        self.assertEqual(self.client.get("/api/auth/login/").status_code, 405)
        self.assertEqual(
            self.client.post(
                "/api/auth/login/", data="[]", content_type="application/json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/login/", data="{", content_type="application/json"
            ).status_code,
            400,
        )
        self.assertEqual(self.client.post("/api/auth/login/", data={}).status_code, 415)

    def test_malformed_reset_fields_return_validation_error(self):
        for data in (
            {"uid": [], "token": "x"},
            {"uid": "invalid", "token": {}},
            {"uid": "invalid", "token": "x"},
        ):
            self.assertEqual(self.post("auth/reset", data).status_code, 400)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class IsolationTests(AccountHelpers):
    def setUp(self):
        self.user_a, self.org_a = self.owner()
        self.user_b = User.objects.create_user(
            email="second@example.test", password=PASSWORD, name="Второй владелец"
        )
        self.org_b = Organization.objects.create(name="Второй центр")
        self.member_b = Membership.objects.create(
            user=self.user_b, organization=self.org_b, role="owner"
        )

    def test_session_lists_only_own_companies(self):
        response = self.client.get("/api/auth/session/")
        self.assertEqual(
            [o["id"] for o in response.json()["organizations"]], [str(self.org_a.id)]
        )
        self.assertEqual(response["Cache-Control"], "no-store, private")

    def test_foreign_company_team_and_audit_are_hidden(self):
        for suffix in ("", "team/", "audit/"):
            self.assertEqual(
                self.client.get(
                    f"/api/organizations/{self.org_b.id}/{suffix}"
                ).status_code,
                404,
            )

    def test_cannot_invite_into_foreign_company(self):
        response = self.post(
            f"organizations/{self.org_b.id}/invitations",
            {"email": "third@example.test", "role": "manager"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Invitation.objects.exists())

    def test_cannot_revoke_foreign_invitation_through_own_company(self):
        self.client.force_login(self.user_b)
        invitation_id, token = self.invitation(self.org_b)
        self.client.force_login(self.user_a)
        self.assertEqual(
            self.post(
                f"organizations/{self.org_a.id}/invitations/{invitation_id}/revoke", {}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.post("invitations/preview", {"token": token}).status_code, 200
        )

    def test_cannot_deactivate_foreign_member_through_own_company(self):
        response = self.post(
            f"organizations/{self.org_a.id}/members/{self.member_b.id}/deactivate", {}
        )
        self.assertEqual(response.status_code, 404)
        self.member_b.refresh_from_db()
        self.assertTrue(self.member_b.is_active)

    def test_manager_cannot_manage_team(self):
        manager = User.objects.create_user(
            email="manager@example.test", password=PASSWORD, name="Менеджер"
        )
        Membership.objects.create(user=manager, organization=self.org_a, role="manager")
        self.client.force_login(manager)
        self.assertEqual(
            self.client.get(f"/api/organizations/{self.org_a.id}/").status_code, 200
        )
        self.assertEqual(
            self.client.get(f"/api/organizations/{self.org_a.id}/team/").status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f"/api/organizations/{self.org_a.id}/audit/").status_code,
            403,
        )
        self.assertEqual(
            self.post(
                f"organizations/{self.org_a.id}/invitations",
                {"email": "third@example.test", "role": "admin"},
            ).status_code,
            403,
        )

    def test_one_user_has_different_roles_in_two_companies(self):
        Membership.objects.create(
            user=self.user_a, organization=self.org_b, role="manager"
        )
        companies = self.client.get("/api/auth/session/").json()["organizations"]
        self.assertEqual(len(companies), 2)
        self.assertEqual(
            self.client.get(f"/api/organizations/{self.org_a.id}/team/").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/organizations/{self.org_b.id}/team/").status_code,
            403,
        )

    def test_deactivation_blocks_existing_session_without_affecting_other_company(self):
        member_a = Membership.objects.create(
            user=self.user_b, organization=self.org_a, role="admin"
        )
        employee_browser = Client()
        employee_browser.force_login(self.user_b)
        self.assertEqual(
            self.post(
                f"organizations/{self.org_a.id}/members/{member_a.id}/deactivate", {}
            ).status_code,
            200,
        )
        self.assertEqual(
            employee_browser.get(f"/api/organizations/{self.org_a.id}/").status_code,
            404,
        )
        self.assertEqual(
            employee_browser.get(f"/api/organizations/{self.org_b.id}/").status_code,
            200,
        )

    def test_owner_cannot_be_deactivated(self):
        owner_membership = Membership.objects.get(user=self.user_a)
        self.assertEqual(
            self.post(
                f"organizations/{self.org_a.id}/members/{owner_membership.id}/deactivate",
                {},
            ).status_code,
            403,
        )
        owner_membership.refresh_from_db()
        self.assertTrue(owner_membership.is_active)

    def test_anonymous_company_access_is_denied(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(f"/api/organizations/{self.org_a.id}/").status_code, 401
        )

    def test_team_and_audit_do_not_leak_invitation_secrets(self):
        _, token = self.invitation(self.org_a)
        for suffix in ("team", "audit"):
            response = self.client.get(f"/api/organizations/{self.org_a.id}/{suffix}/")
            self.assertNotIn(token, response.content.decode())
            self.assertNotIn(digest(token), response.content.decode())
