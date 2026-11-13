import copy
import uuid
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import override_settings
from django.utils import timezone

from crm.integrations import delivery, services
from crm.integrations.address import normalize_domain
from crm.integrations.secrets import decrypt
from crm.integrations.transport import Reply, public_address
from crm.models import AdmissionTransfer, RehubCenter
from crm.services import ApiError
from crm.tests.test_sales import SalesFixtures

TEST_KEY = Fernet.generate_key().decode()


@override_settings(INTEGRATION_ENCRYPTION_KEY=TEST_KEY)
class DeliveryFixtures(SalesFixtures):
    def setUp(self):
        super().setUp()
        self.lead_record = self.lead()
        self.center = services.create_center(
            self.owner,
            self.org.id,
            {"name": "Тестовый центр", "address": "test.rehubpro.kz/qqweqw/qweqwe"},
        )
        self.center = services.update_center(
            self.owner,
            self.org.id,
            self.center.id,
            {"version": 1, "key": "synthetic-key"},
        )
        self.center.verified_at = timezone.now()
        self.center.save()

    def data(self):
        return {
            "center_id": str(self.center.id),
            "version": 1,
            "client_version": 1,
            "last_name": "Тестовый",
            "first_name": "Клиент",
            "date_of_admission": timezone.localdate().isoformat(),
            "confirmed": True,
        }

    def queued(self):
        return services.queue_admission(
            self.owner, self.org.id, self.lead_record.id, self.data()
        )[0]


class DeliveryTests(DeliveryFixtures):
    def test_normalizes_link_and_rejects_unsafe_addresses(self):
        self.assertEqual(self.center.domain, "test.rehubpro.kz")
        for address in (
            "http://test.rehubpro.kz",
            "https://user:password@test.rehubpro.kz",
            "127.0.0.1",
            "https://host.test:8080",
            "file:///tmp/a",
            "https://[::1]",
            "test.rehubpro.kz\\@evil.test",
        ):
            with self.assertRaises(ApiError):
                normalize_domain(address)

    def test_rejects_private_dns_and_mixed_answers(self):
        with patch(
            "socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]
        ):
            with self.assertRaises(ValueError):
                public_address("test.rehubpro.kz")
        with patch(
            "socket.getaddrinfo",
            return_value=[
                (2, 1, 6, "", ("8.8.8.8", 443)),
                (2, 1, 6, "", ("192.168.1.1", 443)),
            ],
        ):
            with self.assertRaises(ValueError):
                public_address("test.rehubpro.kz")

    def test_key_is_encrypted_and_not_returned_by_api(self):
        self.assertNotIn("synthetic-key", self.center.encrypted_key)
        self.assertEqual(decrypt(self.center.encrypted_key), "synthetic-key")
        response = self.client.get("/api/" + self.url("centers") + "/")
        self.assertNotIn("synthetic-key", response.content.decode())
        self.assertNotIn(self.center.encrypted_key, response.content.decode())

    def test_double_confirmation_returns_same_operation(self):
        first = self.queued()
        second, created = services.queue_admission(
            self.owner, self.org.id, self.lead_record.id, self.data()
        )
        self.assertFalse(created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(AdmissionTransfer.objects.count(), 1)
        self.assertNotIn("notes", str(first.payload))

    def test_changed_confirmation_is_conflict(self):
        self.queued()
        data = self.data()
        data["first_name"] = "Другой"
        with self.assertRaises(ApiError) as error:
            services.queue_admission(self.owner, self.org.id, self.lead_record.id, data)
        self.assertEqual(error.exception.status, 409)

    def test_manager_cannot_confirm(self):
        with self.assertRaises(ApiError):
            services.queue_admission(
                self.manager, self.org.id, self.lead_record.id, self.data()
            )

    def test_foreign_center_rejected(self):
        other = services.create_center(
            self.owner,
            self.foreign.id,
            {"name": "Другой", "address": "other.rehubpro.kz"},
        )
        data = self.data()
        data["center_id"] = str(other.id)
        with self.assertRaises(ApiError) as error:
            services.queue_admission(self.owner, self.org.id, self.lead_record.id, data)
        self.assertEqual(error.exception.status, 404)

    def test_preview_version_and_confirmation_are_required(self):
        for change in (
            {"client_version": 0},
            {"version": 0},
            {"confirmed": False},
            {"first_name": ""},
            {"date_of_admission": "2999-01-01"},
        ):
            data = self.data()
            data.update(change)
            with self.assertRaises(ApiError):
                services.queue_admission(
                    self.owner, self.org.id, self.lead_record.id, data
                )
        self.assertFalse(AdmissionTransfer.objects.exists())

    def test_retry_uses_immutable_snapshot_and_same_id(self):
        job = self.queued()
        sent = []

        class Transport:
            def request(self, domain, key, path, payload, operation_id):
                sent.append((copy.deepcopy(payload), operation_id))
                if len(sent) == 1:
                    raise TimeoutError
                return Reply(
                    200,
                    {
                        "status": "delivered",
                        "external_admission_id": operation_id,
                        "resident_id": 42,
                    },
                )

        delivery.deliver_one(Transport())
        job.refresh_from_db()
        self.assertEqual(job.status, "retry")
        self.client_record.name = "Изменённый"
        self.client_record.save()
        AdmissionTransfer.objects.filter(pk=job.id).update(
            next_attempt_at=timezone.now()
        )
        delivery.deliver_one(Transport())
        job.refresh_from_db()
        self.assertEqual(sent[0], sent[1])
        self.assertEqual(job.status, "delivered")
        self.assertEqual(job.attempts.count(), 2)
        self.lead_record.refresh_from_db()
        self.assertEqual(self.lead_record.stage, "new")

    def test_error_classification_and_manual_retry(self):
        self.assertEqual(delivery.classify(Reply(409, {}), uuid.uuid4())[0], "conflict")
        self.assertEqual(delivery.classify(Reply(302, {}), uuid.uuid4())[0], "blocked")
        self.assertEqual(delivery.classify(Reply(401, {}), uuid.uuid4())[0], "blocked")
        self.assertEqual(delivery.classify(Reply(422, {}), uuid.uuid4())[0], "failed")
        job = self.queued()

        class Rejected:
            def request(self, *args):
                return Reply(403, {})

        delivery.deliver_one(Rejected())
        job.refresh_from_db()
        self.assertEqual(job.status, "blocked")
        services.retry_admission(self.owner, self.org.id, job.id)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.attempt_count, 1)

    def test_expired_lease_is_recovered_and_old_worker_cannot_finish(self):
        job = self.queued()
        old = delivery.claim_next()
        AdmissionTransfer.objects.filter(pk=job.id).update(
            lease_until=timezone.now() - timedelta(seconds=1)
        )
        current = delivery.claim_next()
        delivery.finish(old, "delivered", "", resident_id="1")
        job.refresh_from_db()
        self.assertEqual(job.status, "sending")
        delivery.finish(current, "delivered", "", resident_id="2")
        job.refresh_from_db()
        self.assertEqual(job.resident_id, "2")

    def test_disabled_center_and_attempt_limit(self):
        job = self.queued()
        RehubCenter.objects.filter(pk=self.center.id).update(is_active=False)
        delivery.deliver_one()
        job.refresh_from_db()
        self.assertEqual(job.status, "blocked")
        AdmissionTransfer.objects.filter(pk=job.id).update(
            status="pending", cycle_attempts=8
        )
        self.assertIsNone(delivery.claim_next())
        job.refresh_from_db()
        self.assertEqual(job.status, "failed")

    def test_untrusted_health_does_not_verify_center(self):
        class WrongCenter:
            def request(self, *args):
                return Reply(
                    200,
                    {
                        "schema_version": 1,
                        "company_id": str(self.org.id)
                        if hasattr(self, "org")
                        else "wrong",
                        "connection_id": "wrong",
                    },
                )

        with self.assertRaises(ApiError):
            services.verify_center(
                self.owner, self.org.id, self.center.id, WrongCenter()
            )

    def test_domain_cannot_change_after_queueing(self):
        self.queued()
        with self.assertRaises(ApiError):
            services.update_center(
                self.owner,
                self.org.id,
                self.center.id,
                {"version": self.center.version, "address": "other.rehubpro.kz"},
            )
