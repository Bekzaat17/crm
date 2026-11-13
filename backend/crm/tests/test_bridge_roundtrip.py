"""Запускать с --settings=crm.tests.bridge_settings: обе стороны без имитации сохранения Resident."""

import unittest
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.test import Client
from django.utils import timezone

from crm.integrations import delivery, services
from crm.integrations.transport import Reply
from crm.models import AdmissionTransfer
from crm.tests.test_delivery import DeliveryFixtures


@unittest.skipUnless(apps.is_installed("crm_bridge"), "Изолированный сквозной набор")
class RoundtripTests(DeliveryFixtures):
    def test_lost_response_replay_creates_one_real_resident(self):
        from crm_bridge.models import AdmissionReceipt, CrmCredential
        from crm_bridge.services.admission_service import token_hash
        from residents.models import Resident

        CrmCredential.objects.create(
            company_id=self.org.id,
            connection_id=self.center.id,
            token_hash=token_hash("synthetic-key"),
            expires_at=timezone.now() + timedelta(days=1),
        )
        receiver = Client(enforce_csrf_checks=True)

        class Loopback:
            calls = 0

            def request(self, domain, key, path, payload=None, operation_id=""):
                if payload is None:
                    response = receiver.get(path, HTTP_AUTHORIZATION=f"Bearer {key}")
                    return Reply(response.status_code, response.json())
                self.calls += 1
                response = receiver.post(
                    path,
                    data=payload,
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {key}",
                    HTTP_IDEMPOTENCY_KEY=operation_id,
                )
                if self.calls == 1:
                    assert response.status_code == 201, response.content
                    raise TimeoutError("Ответ потерян после commit")
                return Reply(response.status_code, response.json())

        transport = Loopback()
        job = self.queued()
        with patch(
            "licenses.services.license_service.LicenseService.get_status",
            return_value="ok",
        ):
            services.verify_center(self.owner, self.org.id, self.center.id, transport)
            delivery.deliver_one(transport)
            self.assertEqual(Resident.objects.count(), 1)
            AdmissionTransfer.objects.filter(pk=job.id).update(
                next_attempt_at=timezone.now()
            )
            delivery.deliver_one(transport)
        job.refresh_from_db()
        self.assertEqual(job.status, "delivered")
        self.assertEqual(Resident.objects.count(), 1)
        self.assertEqual(AdmissionReceipt.objects.count(), 1)
