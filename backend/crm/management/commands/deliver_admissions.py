import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from crm.integrations.delivery import deliver_one


class Command(BaseCommand):
    help = (
        "Доставляет очередь поступлений. Запускать отдельным процессом под supervisor."
    )

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        try:
            while True:
                close_old_connections()
                processed = deliver_one()
                if options["once"]:
                    break
                if not processed:
                    time.sleep(2)
        except KeyboardInterrupt:
            return
