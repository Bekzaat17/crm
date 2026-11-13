import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from crm.integrations.delivery import deliver_one
from crm.notifications.dispatch import dispatch_one
from crm.notifications.reminders import schedule_reminders

REMINDER_INTERVAL = 60


class Command(BaseCommand):
    help = (
        "Фоновый исполнитель: передачи в RehubPro, очередь сообщений и "
        "напоминания. Запускать отдельным процессом под supervisor."
    )

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        next_reminders = 0.0
        try:
            while True:
                close_old_connections()
                if time.monotonic() >= next_reminders:
                    schedule_reminders()
                    next_reminders = time.monotonic() + REMINDER_INTERVAL
                busy = deliver_one()
                busy = dispatch_one() or busy
                if options["once"]:
                    break
                if not busy:
                    time.sleep(2)
        except KeyboardInterrupt:
            return
