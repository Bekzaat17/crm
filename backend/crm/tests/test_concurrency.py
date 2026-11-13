from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from django.utils import timezone

from crm.core.errors import ApiError
from crm.core.throttle import throttle
from crm.core.tokens import digest
from crm.models import (
    AuditEvent,
    Invitation,
    Membership,
    Organization,
    RateLimitBucket,
    User,
)
from crm.organizations.services import accept_invitation
from crm.sales.pipeline import create_default_stages


@skipUnless(
    connection.vendor == "postgresql",
    "Конкурентные транзакции проверяются на PostgreSQL",
)
class ConcurrencyTests(TransactionTestCase):
    def test_parallel_acceptance_creates_exactly_one_membership(self):
        user = User.objects.create_user(
            email="worker@example.test", name="Сотрудник", password="Forest-River-2748!"
        )
        owner = User.objects.create_user(
            email="owner@example.test", name="Владелец", password="Forest-River-2748!"
        )
        organization = Organization.objects.create(name="Центр")
        token = "synthetic-concurrent-invitation-token"
        Invitation.objects.create(
            organization=organization,
            email=user.email,
            role="manager",
            invited_by=owner,
            token_hash=digest(token),
            expires_at=timezone.now() + timedelta(days=1),
        )
        barrier = Barrier(2)

        def accept():
            close_old_connections()
            try:
                actor = User.objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                try:
                    accept_invitation(token, actor, {})
                    return "accepted"
                except ApiError:
                    return "closed"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: accept(), range(2)))
        self.assertCountEqual(results, ["accepted", "closed"])
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(action="invitation.accepted").count(), 1
        )

    def test_shared_throttle_does_not_lose_parallel_increments(self):
        barrier = Barrier(6)

        def increment():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                throttle("concurrent-test", "synthetic", 10)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: increment(), range(6)))
        self.assertEqual(RateLimitBucket.objects.get().count, 6)

    def test_parallel_lead_edits_detect_stale_version(self):
        from crm.models import Branch, Client
        from crm.sales import services as sales

        actor = User.objects.create_user(
            email="sales-concurrent@example.test",
            name="Владелец",
            password="Forest-River-2748!",
        )
        org = Organization.objects.create(name="Центр")
        create_default_stages(org)
        membership = Membership.objects.create(
            user=actor, organization=org, role="owner"
        )
        branch = Branch.objects.create(organization=org, name="Основной")
        client = Client.objects.create(
            organization=org, created_by=actor, name="Клиент"
        )
        lead = sales.create_lead(
            actor,
            org.id,
            dict(
                client_id=str(client.id),
                assignee_id=str(membership.id),
                branch_id=str(branch.id),
                title="Консультация",
            ),
        )
        barrier = Barrier(2)

        def update(stage):
            close_old_connections()
            try:
                user = User.objects.get(pk=actor.pk)
                barrier.wait(timeout=10)
                try:
                    sales.update_lead(
                        user, org.id, lead.id, {"version": 1, "stage": stage}
                    )
                    return "updated"
                except ApiError as error:
                    return error.status
            finally:
                connections.close_all()

        stages = [
            str(org.pipeline_stages.get(name=name).id)
            for name in ("В работе", "Консультация")
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, stages))
        self.assertCountEqual(results, ["updated", 409])
        lead.refresh_from_db()
        self.assertEqual(lead.version, 2)

    def test_parallel_workers_cannot_claim_same_transfer(self):
        from crm.models import AdmissionTransfer, Branch, Client, Lead, RehubCenter

        owner = User.objects.create_user(
            email="outbox@example.test", name="Владелец", password="Forest-River-2748!"
        )
        org = Organization.objects.create(name="Центр")
        member = Membership.objects.create(user=owner, organization=org, role="owner")
        branch = Branch.objects.create(organization=org, name="Основной")
        create_default_stages(org)
        client = Client.objects.create(
            organization=org, created_by=owner, name="Тестовый клиент"
        )
        lead = Lead.objects.create(
            organization=org,
            client=client,
            assignee=member,
            branch=branch,
            title="Поступление",
            stage=org.pipeline_stages.get(name="Новое"),
        )
        center = RehubCenter.objects.create(
            organization=org,
            name="Центр",
            domain="test.rehubpro.kz",
            verified_at=timezone.now(),
        )
        job = AdmissionTransfer.objects.create(
            lead=lead, center=center, payload={}, confirmed_by=owner
        )
        barrier = Barrier(2)

        def claim(_):
            from crm.integrations.delivery import claim_next

            close_old_connections()
            try:
                barrier.wait(timeout=10)
                result = claim_next()
                return str(result.id) if result else None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        self.assertCountEqual(results, [str(job.id), None])
        job.refresh_from_db()
        self.assertEqual(job.attempt_count, 1)
