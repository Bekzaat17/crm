from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from crm.models import (
    FollowUpTask,
    Lead,
    NotificationPreference,
    OutboundMessage,
    PushSubscription,
    ReminderDispatch,
    TelegramCursor,
    TelegramLink,
    TelegramLinkToken,
)
from crm.notifications import telegram_link
from crm.notifications.channels import TelegramChannel, WebPushChannel
from crm.notifications.dispatch import claim_next, dispatch_all
from crm.notifications.reminders import schedule_reminders
from crm.notifications.services import enqueue
from crm.notifications.telegram import BotApiClient, TelegramError
from crm.notifications.webpush import PushError
from crm.tests.test_sales import SalesFixtures

TOKEN = "123456:synthetic-test-token"
CONFIGURED = dict(
    TELEGRAM_BOT_TOKEN=TOKEN,
    TELEGRAM_BOT_USERNAME="rehub_test_bot",
    VAPID_PUBLIC_KEY="synthetic-public",
    VAPID_PRIVATE_KEY="synthetic-private",
)
FCM = "https://fcm.googleapis.com/fcm/send/synthetic"


class FakeTelegram:
    def __init__(self, error=None, updates=()):
        self.sent, self.error, self.updates = [], error, list(updates)

    def send_message(self, chat_id, text):
        if self.error:
            raise self.error
        self.sent.append((chat_id, text))

    def get_updates(self, offset, timeout):
        return [u for u in self.updates if u["update_id"] >= offset]


class FakePush:
    def __init__(self, status=None):
        self.sent, self.status = [], status

    def send(self, subscription, payload, ttl):
        if self.status:
            raise PushError(self.status)
        self.sent.append((subscription.endpoint, payload))


def channels(telegram=None, push=None):
    return {
        "telegram": TelegramChannel(telegram or FakeTelegram()),
        "webpush": WebPushChannel(push or FakePush()),
    }


@override_settings(**CONFIGURED)
class ReminderTests(SalesFixtures):
    def setUp(self):
        super().setUp()
        TelegramLink.objects.create(user=self.manager, chat_id=1001)
        PushSubscription.objects.create(
            user=self.manager, endpoint=FCM, p256dh="key", auth="auth"
        )
        self.lead_record = self.lead()
        self.task = FollowUpTask.objects.create(
            lead=self.lead_record,
            title="Позвонить Тестовому клиенту",
            due_at=timezone.now() - timedelta(minutes=5),
            created_by=self.owner,
        )

    def test_overdue_task_queues_one_reminder_per_channel(self):
        self.assertEqual(schedule_reminders(), 1)
        self.assertEqual(schedule_reminders(), 0)
        channels_used = set(OutboundMessage.objects.values_list("channel", flat=True))
        self.assertEqual(channels_used, {"telegram", "webpush"})

    def test_reminder_text_is_neutral_and_links_to_lead(self):
        schedule_reminders()
        telegram = FakeTelegram()
        push = FakePush()
        dispatch_all(channels(telegram, push))
        text = telegram.sent[0][1]
        self.assertNotIn("Тестов", text)
        self.assertIn(f"/leads/{self.lead_record.id}", text)
        self.assertEqual(
            push.sent[0][1]["url"], f"/c/{self.org.id}/leads/{self.lead_record.id}"
        )
        message = OutboundMessage.objects.first()
        self.assertEqual((message.status, message.body), ("sent", ""))

    def test_rescheduled_task_creates_new_reminder(self):
        schedule_reminders()
        self.task.due_at = timezone.now() - timedelta(minutes=1)
        self.task.save()
        self.assertEqual(schedule_reminders(), 1)
        self.assertEqual(ReminderDispatch.objects.count(), 2)

    def test_no_reminders_for_completed_old_or_inactive(self):
        FollowUpTask.objects.update(completed_at=timezone.now())
        self.assertEqual(schedule_reminders(), 0)
        FollowUpTask.objects.update(
            completed_at=None, due_at=timezone.now() - timedelta(days=2)
        )
        self.assertEqual(schedule_reminders(), 0)
        FollowUpTask.objects.update(due_at=timezone.now() - timedelta(minutes=1))
        self.member.is_active = False
        self.member.save()
        self.assertEqual(schedule_reminders(), 0)

    def test_contact_reminder_only_for_open_stage(self):
        FollowUpTask.objects.all().delete()
        due = timezone.now() - timedelta(minutes=1)
        Lead.objects.filter(pk=self.lead_record.pk).update(next_contact_at=due)
        admitted = self.org.pipeline_stages.get(kind="admitted")
        Lead.objects.filter(pk=self.lead_record.pk).update(stage=admitted)
        self.assertEqual(schedule_reminders(), 0)
        Lead.objects.filter(pk=self.lead_record.pk).update(
            stage=self.org.pipeline_stages.get(name="Новое")
        )
        self.assertEqual(schedule_reminders(), 1)

    def test_preferences_disable_channel(self):
        NotificationPreference.objects.create(user=self.manager, telegram=False)
        schedule_reminders()
        self.assertEqual(
            list(OutboundMessage.objects.values_list("channel", flat=True)),
            ["webpush"],
        )

    def test_telegram_403_blocks_link_and_429_retries(self):
        schedule_reminders()
        OutboundMessage.objects.filter(channel="webpush").delete()
        dispatch_all(channels(FakeTelegram(TelegramError(429, "http_429", 30))))
        message = OutboundMessage.objects.get()
        self.assertEqual(message.status, "retry")
        self.assertGreaterEqual(
            message.next_attempt_at, timezone.now() + timedelta(seconds=25)
        )
        OutboundMessage.objects.update(next_attempt_at=timezone.now())
        dispatch_all(channels(FakeTelegram(TelegramError(403, "http_403"))))
        message.refresh_from_db()
        self.assertEqual(message.status, "failed")
        self.assertTrue(TelegramLink.objects.get(user=self.manager).is_blocked)

    def test_gone_push_subscription_is_removed(self):
        schedule_reminders()
        OutboundMessage.objects.filter(channel="telegram").delete()
        dispatch_all(channels(push=FakePush(410)))
        self.assertFalse(PushSubscription.objects.exists())
        self.assertEqual(OutboundMessage.objects.get().status, "failed")


@override_settings(**CONFIGURED)
class TelegramLinkTests(SalesFixtures):
    def start(self, token, update_id=1, chat_type="private", chat_id=5005):
        return {
            "update_id": update_id,
            "message": {
                "chat": {"id": chat_id, "type": chat_type},
                "text": f"/start {token}",
            },
        }

    def test_link_api_and_single_use_token(self):
        response = self.post("me/telegram/link", {})
        url = response.json()["url"]
        self.assertTrue(url.startswith("https://t.me/rehub_test_bot?start="))
        token = url.split("start=")[1]
        bot = FakeTelegram(
            updates=[self.start(token), self.start(token, 2, chat_id=6006)]
        )
        telegram_link.poll_once(bot, timeout=0)
        link = TelegramLink.objects.get(user=self.owner)
        self.assertEqual(link.chat_id, 5005)
        self.assertIn("недействительна", bot.sent[-1][1])
        self.assertEqual(TelegramCursor.objects.get().offset, 2)
        telegram_link.poll_once(bot, timeout=0)
        self.assertEqual(len(bot.sent), 2)

    def test_group_chat_and_expired_token_are_ignored(self):
        url, _ = telegram_link.create_link(self.owner)
        token = url.split("start=")[1]
        bot = FakeTelegram()
        telegram_link.handle_update(self.start(token, chat_type="group"), bot)
        self.assertFalse(TelegramLink.objects.exists())
        TelegramLinkToken.objects.update(expires_at=timezone.now())
        telegram_link.handle_update(self.start(token), bot)
        self.assertFalse(TelegramLink.objects.exists())

    def test_stop_blocks_notifications(self):
        TelegramLink.objects.create(user=self.owner, chat_id=5005)
        update = {
            "update_id": 1,
            "message": {"chat": {"id": 5005, "type": "private"}, "text": "/stop"},
        }
        telegram_link.handle_update(update, FakeTelegram())
        self.assertTrue(TelegramLink.objects.get().is_blocked)

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_link_requires_configured_bot(self):
        self.assertEqual(self.post("me/telegram/link", {}).status_code, 503)

    def test_transport_error_does_not_expose_token(self):
        with patch(
            "crm.notifications.telegram.http.client.HTTPSConnection.request",
            side_effect=OSError(f"failed /bot{TOKEN}/sendMessage"),
        ):
            with self.assertRaises(TelegramError) as caught:
                BotApiClient(TOKEN).send_message(1, "text")
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertIsNone(caught.exception.__context__ and caught.exception.__cause__)


@override_settings(**CONFIGURED)
class PushApiTests(SalesFixtures):
    def subscription(self, endpoint=FCM):
        return {"endpoint": endpoint, "keys": {"p256dh": "key", "auth": "auth"}}

    def test_subscribe_validates_push_service(self):
        response = self.post("me/push/subscribe", self.subscription())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["webpush"]["subscriptions"], 1)
        for endpoint in (
            "https://127.0.0.1/push",
            "http://fcm.googleapis.com/x",
            "https://evil.example/fcm.googleapis.com",
        ):
            self.assertEqual(
                self.post("me/push/subscribe", self.subscription(endpoint)).status_code,
                400,
            )

    def test_unsubscribe_only_own_subscription(self):
        PushSubscription.objects.create(
            user=self.manager, endpoint=FCM, p256dh="key", auth="auth"
        )
        self.post("me/push/unsubscribe", {"endpoint": FCM})
        self.assertTrue(PushSubscription.objects.exists())

    def test_preferences_update_and_validation(self):
        response = self.post("me/notifications", {"email": True, "telegram": False})
        self.assertEqual(
            response.json()["preferences"],
            {"email": True, "telegram": False, "webpush": True},
        )
        self.assertEqual(
            self.post("me/notifications", {"email": "yes"}).status_code, 400
        )


@skipUnless(
    connection.vendor == "postgresql",
    "Конкурентные транзакции проверяются на PostgreSQL",
)
class OutboxConcurrencyTests(TransactionTestCase):
    def test_parallel_workers_claim_message_once(self):
        enqueue(
            channel="email",
            kind="test",
            dedup_key="concurrency",
            subject="Тема",
            body="Текст",
            address="worker@example.test",
        )
        barrier = Barrier(2)

        def claim(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                job = claim_next()
                return str(job.pk) if job else None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        self.assertEqual(len([r for r in results if r]), 1)
        self.assertEqual(OutboundMessage.objects.get().attempts, 1)
