import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from crm.notifications.telegram import TelegramError, default_client
from crm.notifications.telegram_link import poll_once

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Получает команды Telegram-бота (long polling). Нужен один процесс."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        client = default_client()
        if client is None:
            raise CommandError("Задайте CRM_TELEGRAM_BOT_TOKEN.")
        try:
            while True:
                close_old_connections()
                try:
                    poll_once(client, timeout=0 if options["once"] else 25)
                except TelegramError as exc:
                    # Только код ошибки: путь запроса содержит токен бота.
                    logger.warning("Telegram недоступен: %s", exc.code)
                    time.sleep(5)
                if options["once"]:
                    break
        except KeyboardInterrupt:
            return
