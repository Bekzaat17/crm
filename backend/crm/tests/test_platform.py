import json
import os
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import Client, TestCase, override_settings

from crm.models import Invitation, Membership, Organization, PipelineStage, User
from crm.notifications.dispatch import dispatch_all

PASSWORD = "Granite-Harbor-6153!"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PlatformTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="platform@example.test", password=PASSWORD, name="Платформа"
        )
        self.client.force_login(self.admin)

    def post(self, path, data, client=None):
        return (client or self.client).post(
            f"/api/{path}/", data=json.dumps(data), content_type="application/json"
        )

    def test_registration_endpoints_are_gone(self):
        self.assertEqual(self.post("auth/register", {}).status_code, 404)
        self.assertEqual(self.post("auth/verify", {}).status_code, 404)

    def test_only_platform_admin_creates_companies(self):
        user = User.objects.create_user(
            email="owner@example.test", password=PASSWORD, name="Владелец"
        )
        other = Client()
        other.force_login(user)
        response = self.post("platform/companies", {"name": "Центр"}, other)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(other.get("/api/platform/companies/").status_code, 403)
        self.assertFalse(Organization.objects.exists())

    def test_admin_owns_company_without_owner_email(self):
        response = self.post("platform/companies", {"name": "Первый центр"})
        self.assertEqual(response.status_code, 201, response.content)
        org = Organization.objects.get()
        self.assertEqual(Membership.objects.get(organization=org).role, "owner")
        self.assertEqual(PipelineStage.objects.filter(organization=org).count(), 6)
        self.assertEqual(org.branches.count(), 1)
        listed = self.client.get("/api/platform/companies/").json()["items"]
        self.assertEqual(listed[0]["owner"]["state"], "active")

    def test_owner_invitation_flow(self):
        response = self.post(
            "platform/companies",
            {"name": "Центр", "owner_email": "Owner@Example.test"},
        )
        org = Organization.objects.get(pk=response.json()["id"])
        self.assertFalse(Membership.objects.filter(organization=org).exists())
        invitation = Invitation.objects.get(organization=org)
        self.assertEqual(
            (invitation.role, invitation.email), ("owner", "owner@example.test")
        )
        dispatch_all()
        token = mail.outbox[-1].body.split("token=")[1].split()[0]
        guest = Client()
        accepted = self.post(
            "invitations/accept",
            {"token": token, "name": "Владелец", "password": PASSWORD},
            guest,
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)
        owner = Membership.objects.get(organization=org)
        self.assertEqual(
            (owner.role, owner.user.email), ("owner", "owner@example.test")
        )
        again = self.post(
            f"platform/companies/{org.id}/owner-invitation",
            {"owner_email": "second@example.test"},
        )
        self.assertEqual(again.status_code, 409)

    def test_platform_admin_has_no_access_to_foreign_company_data(self):
        response = self.post(
            "platform/companies", {"name": "Центр", "owner_email": "o@example.test"}
        )
        org_id = response.json()["id"]
        self.assertEqual(
            self.client.get(f"/api/organizations/{org_id}/").status_code, 404
        )

    def test_company_creation_is_atomic(self):
        with patch(
            "crm.platform_admin.services.create_default_stages",
            side_effect=RuntimeError("test"),
        ):
            with self.assertRaises(RuntimeError):
                self.post("platform/companies", {"name": "Центр"})
        self.assertFalse(Organization.objects.exists())

    def test_session_marks_platform_admin(self):
        user = self.client.get("/api/auth/session/").json()["user"]
        self.assertTrue(user["is_platform_admin"])


class EnsureSuperuserTests(TestCase):
    def run_command(self, env, *args):
        with patch.dict(os.environ, env, clear=False):
            call_command("ensure_superuser", *args, stdout=StringIO())

    def test_creates_and_keeps_password_unless_reset(self):
        env = {
            "CRM_SUPERUSER_EMAIL": "Admin@Example.test",
            "CRM_SUPERUSER_PASSWORD": PASSWORD,
        }
        self.run_command(env)
        user = User.objects.get(email="admin@example.test")
        self.assertTrue(user.is_superuser and user.check_password(PASSWORD))
        new = "Copper-Meadow-8274!"
        self.run_command({**env, "CRM_SUPERUSER_PASSWORD": new})
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))
        self.run_command({**env, "CRM_SUPERUSER_PASSWORD": new}, "--reset-password")
        user.refresh_from_db()
        self.assertTrue(user.check_password(new))

    def test_rejects_missing_or_weak_password(self):
        with self.assertRaises(CommandError):
            self.run_command({"CRM_SUPERUSER_EMAIL": "", "CRM_SUPERUSER_PASSWORD": ""})
        with self.assertRaises(CommandError):
            self.run_command(
                {
                    "CRM_SUPERUSER_EMAIL": "a@example.test",
                    "CRM_SUPERUSER_PASSWORD": "123",
                }
            )
