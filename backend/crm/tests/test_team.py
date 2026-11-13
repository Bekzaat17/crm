from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from crm.core.errors import ApiError
from crm.models import AuditEvent, Branch, Membership, Organization, User
from crm.organizations.services import transfer_ownership
from crm.tests.test_sales import SalesFixtures

PASSWORD = "Sales-River-5748!"


class TeamFixtures(SalesFixtures):
    def setUp(self):
        super().setUp()
        self.admin_user = User.objects.create_user(
            email="admin@sales.test", name="Администратор", password=PASSWORD
        )
        self.admin = Membership.objects.create(
            user=self.admin_user, organization=self.org, role="admin"
        )

    def role(self, member, role):
        return self.post(self.url(f"members/{member.id}/role"), {"role": role})


class RoleTests(TeamFixtures):
    def test_owner_promotes_manager_to_lead_and_audits(self):
        response = self.role(self.member, "lead")
        self.assertEqual(response.status_code, 200, response.content)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, "lead")
        self.assertTrue(
            AuditEvent.objects.filter(action="membership.role_changed").exists()
        )

    def test_owner_role_is_not_assignable(self):
        self.assertEqual(self.role(self.member, "owner").status_code, 400)

    def test_admin_cannot_grant_admin_or_touch_other_admin(self):
        self.client.force_login(self.admin_user)
        self.assertEqual(self.role(self.member, "admin").status_code, 403)
        other = Membership.objects.create(
            user=User.objects.create_user(
                email="admin2@sales.test", name="Второй", password=PASSWORD
            ),
            organization=self.org,
            role="admin",
        )
        self.assertEqual(self.role(other, "manager").status_code, 403)
        self.assertEqual(self.role(self.member, "lead").status_code, 200)

    def test_admin_cannot_invite_admin(self):
        self.client.force_login(self.admin_user)
        response = self.post(
            self.url("invitations"), {"email": "x@sales.test", "role": "admin"}
        )
        self.assertEqual(response.status_code, 403)

    def test_own_role_and_foreign_member_are_rejected(self):
        self.assertEqual(self.role(self.owner_member, "admin").status_code, 403)
        foreign = self.post(
            self.url(f"members/{self.foreign_member.id}/role"), {"role": "lead"}
        )
        self.assertEqual(foreign.status_code, 404)

    def test_manager_cannot_change_roles(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.role(self.admin, "manager").status_code, 403)

    def test_team_marks_manageable_members(self):
        self.client.force_login(self.admin_user)
        members = {
            m["role"]: m["manageable"]
            for m in self.client.get(f"/api/{self.url('team')}/").json()["members"]
        }
        self.assertEqual(members, {"owner": False, "manager": True, "admin": False})


class OwnershipTests(TeamFixtures):
    def transfer(self, member, password=PASSWORD):
        return self.post(
            self.url("ownership"),
            {"membership_id": str(member.id), "password": password},
        )

    def test_transfer_requires_password(self):
        self.assertEqual(self.transfer(self.admin, "wrong").status_code, 403)
        self.owner_member.refresh_from_db()
        self.assertEqual(self.owner_member.role, "owner")

    def test_transfer_swaps_roles(self):
        self.assertEqual(self.transfer(self.admin).status_code, 200)
        self.owner_member.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertEqual((self.owner_member.role, self.admin.role), ("admin", "owner"))
        self.assertEqual(self.transfer(self.member).status_code, 403)

    def test_admin_cannot_transfer_and_foreign_target_is_rejected(self):
        self.assertEqual(self.transfer(self.foreign_member).status_code, 404)
        self.client.force_login(self.admin_user)
        self.assertEqual(self.transfer(self.member).status_code, 403)

    def test_inactive_target_is_rejected(self):
        self.member.is_active = False
        self.member.save()
        self.assertEqual(self.transfer(self.member).status_code, 409)


class BranchTests(TeamFixtures):
    def test_create_rename_archive_restore(self):
        created = self.post(self.url("branches"), {"name": "Второй филиал"})
        self.assertEqual(created.status_code, 201, created.content)
        branch = created.json()
        renamed = self.post(
            self.url(f"branches/{branch['id']}"),
            {"name": "Филиал Север", "version": branch["version"]},
        )
        self.assertEqual(renamed.json()["name"], "Филиал Север")
        stale = self.post(
            self.url(f"branches/{branch['id']}"), {"name": "X", "version": 1}
        )
        self.assertEqual(stale.status_code, 409)
        archived = self.post(self.url(f"branches/{branch['id']}/archive"), {})
        self.assertFalse(archived.json()["is_active"])
        with self.assertRaises(ApiError):
            self.lead(branch_id=branch["id"])
        restored = self.post(self.url(f"branches/{branch['id']}/restore"), {})
        self.assertTrue(restored.json()["is_active"])

    def test_last_active_branch_is_kept(self):
        response = self.post(self.url(f"branches/{self.branch.id}/archive"), {})
        self.assertEqual(response.status_code, 409)

    def test_duplicate_name_and_manager_access(self):
        self.assertEqual(
            self.post(self.url("branches"), {"name": "основной"}).status_code, 409
        )
        self.client.force_login(self.manager)
        self.assertEqual(
            self.post(self.url("branches"), {"name": "Ещё"}).status_code, 403
        )
        listed = self.client.get(f"/api/{self.url('branches')}/?archived=1").json()
        self.assertEqual([b["name"] for b in listed["items"]], ["Основной"])

    def test_foreign_branch_is_not_found(self):
        response = self.post(self.url(f"branches/{self.foreign_branch.id}/archive"), {})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Branch.objects.get(pk=self.foreign_branch.pk).is_active)


class ContactTests(TeamFixtures):
    def contact(self):
        response = self.post(
            self.url(f"clients/{self.client_record.id}/contacts"),
            {"name": "Тестовая мама", "relationship": "Мать", "phone": "+70000000001"},
        )
        return response.json()["id"]

    def test_update_with_version_and_delete(self):
        contact_id = self.contact()
        path = self.url(f"clients/{self.client_record.id}/contacts/{contact_id}")
        data = {"name": "Тестовый отец", "relationship": "Отец", "version": 1}
        self.assertEqual(self.post(path, data).json()["version"], 2)
        self.assertEqual(self.post(path, data).status_code, 409)
        self.assertEqual(self.post(path + "/delete", {}).status_code, 200)
        detail = self.client.get(
            f"/api/{self.url(f'clients/{self.client_record.id}')}/"
        )
        self.assertEqual(detail.json()["contacts"], [])

    def test_contact_of_foreign_client_is_not_found(self):
        foreign = self.post(
            f"organizations/{self.foreign.id}/clients/{self.foreign_client.id}/contacts",
            {"name": "Чужой", "relationship": "Брат"},
        ).json()["id"]
        path = self.url(f"clients/{self.client_record.id}/contacts/{foreign}/delete")
        self.assertEqual(self.post(path, {}).status_code, 404)

    def test_manager_without_access_to_client_cannot_edit_contact(self):
        contact_id = self.contact()
        self.client.force_login(self.manager)
        path = self.url(f"clients/{self.client_record.id}/contacts/{contact_id}/delete")
        self.assertEqual(self.post(path, {}).status_code, 404)


@skipUnless(
    connection.vendor == "postgresql",
    "Конкурентные транзакции проверяются на PostgreSQL",
)
class OwnershipConcurrencyTests(TransactionTestCase):
    def test_parallel_transfers_leave_single_owner(self):
        org = Organization.objects.create(name="Центр")
        owner = User.objects.create_user(
            email="owner@team.test", name="Владелец", password=PASSWORD
        )
        Membership.objects.create(user=owner, organization=org, role="owner")
        targets = [
            Membership.objects.create(
                user=User.objects.create_user(
                    email=f"t{i}@team.test", name=f"Сотрудник {i}", password=PASSWORD
                ),
                organization=org,
                role="admin",
            )
            for i in range(2)
        ]
        barrier = Barrier(2)

        def transfer(target):
            close_old_connections()
            try:
                actor = User.objects.get(pk=owner.pk)
                barrier.wait(timeout=10)
                try:
                    transfer_ownership(
                        actor,
                        org.id,
                        {"membership_id": str(target.id), "password": PASSWORD},
                    )
                    return "done"
                except ApiError as error:
                    return error.status
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(transfer, targets))
        self.assertCountEqual(results, ["done", 403])
        self.assertEqual(
            Membership.objects.filter(organization=org, role="owner").count(), 1
        )
