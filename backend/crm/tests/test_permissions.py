from django.test import SimpleTestCase

from crm.core.errors import ApiError
from crm.organizations.models import Membership
from crm.organizations.permissions import (
    POLICIES,
    AssignedScope,
    CompanyScope,
    Perm,
    can,
    granted,
    require,
)
from crm.sales.lead_changes import ChangeContext, apply_changes
from crm.tests.test_sales import SalesFixtures


def member(role):
    return Membership(role=role)


class RolePolicyTests(SimpleTestCase):
    def test_every_role_has_policy(self):
        self.assertEqual(set(POLICIES), set(Membership.Role))

    def test_owner_only_transfers_ownership(self):
        allowed = [
            r for r in Membership.Role if can(member(r), Perm.TRANSFER_OWNERSHIP)
        ]
        self.assertEqual(allowed, [Membership.Role.OWNER])

    def test_admin_manages_team_but_lead_and_manager_do_not(self):
        self.assertTrue(can(member("admin"), Perm.MANAGE_TEAM))
        self.assertFalse(can(member("lead"), Perm.MANAGE_TEAM))
        self.assertFalse(can(member("manager"), Perm.MANAGE_TEAM))

    def test_lead_sends_admissions_and_sees_company(self):
        self.assertTrue(can(member("lead"), Perm.SEND_ADMISSIONS))
        self.assertIsInstance(POLICIES["lead"].scope, CompanyScope)

    def test_manager_has_no_permissions_and_assigned_scope(self):
        self.assertEqual(granted(member("manager")), [])
        self.assertIsInstance(POLICIES["manager"].scope, AssignedScope)

    def test_require_raises_forbidden_with_message(self):
        with self.assertRaises(ApiError) as caught:
            require(member("manager"), Perm.SEND_ADMISSIONS)
        self.assertEqual(caught.exception.status, 403)
        self.assertIn("руководитель", caught.exception.message)


class LeadChangeRulesTests(SalesFixtures):
    def apply(self, lead, data, actor_member=None):
        ctx = ChangeContext(
            actor_member or self.owner_member,
            self.org.id,
            lambda company, value: Membership.objects.get(pk=value),
        )
        return apply_changes(lead, data, ctx)

    def test_unchanged_fields_produce_no_history(self):
        lead = self.lead()
        self.assertEqual(self.apply(lead, {"title": lead.title, "source": ""}), [])

    def test_refusal_requires_reason(self):
        with self.assertRaises(ApiError):
            self.apply(self.lead(), {"stage": self.stage("Отказ")})

    def test_leaving_refused_stage_clears_reason(self):
        lead = self.lead()
        self.apply(lead, {"stage": self.stage("Отказ"), "refusal_reason": "Причина"})
        changes = self.apply(lead, {"stage": self.stage("В работе")})
        self.assertEqual(lead.refusal_reason, "")
        self.assertIn("Этап: Отказ → В работе", changes)

    def test_manager_cannot_reassign(self):
        lead = self.lead()
        with self.assertRaises(ApiError) as caught:
            self.apply(lead, {"assignee_id": str(self.owner_member.id)}, self.member)
        self.assertEqual(caught.exception.status, 403)

    def test_naive_next_contact_is_rejected(self):
        with self.assertRaises(ApiError):
            self.apply(self.lead(), {"next_contact_at": "2026-11-20T10:00:00"})
