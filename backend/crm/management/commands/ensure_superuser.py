import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from crm.accounts.models import User


class Command(BaseCommand):
    help = (
        "Создаёт администратора платформы из CRM_SUPERUSER_EMAIL и "
        "CRM_SUPERUSER_PASSWORD. Пароль существующего аккаунта не меняется "
        "без --reset-password."
    )

    def add_arguments(self, parser):
        parser.add_argument("--reset-password", action="store_true")

    def handle(self, *args, **options):
        email = os.getenv("CRM_SUPERUSER_EMAIL", "").strip().lower()
        password = os.getenv("CRM_SUPERUSER_PASSWORD", "")
        name = os.getenv("CRM_SUPERUSER_NAME", "Администратор платформы").strip()
        if not email or not password:
            raise CommandError("Задайте CRM_SUPERUSER_EMAIL и CRM_SUPERUSER_PASSWORD.")
        user = User.objects.filter(email__iexact=email).first()
        try:
            validate_password(password, user or User(email=email, name=name))
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages))
        if user is None:
            User.objects.create_superuser(email=email, password=password, name=name)
            self.stdout.write(f"Создан администратор платформы {email}.")
            return
        user.is_superuser = user.is_staff = user.is_active = True
        fields = ["is_superuser", "is_staff", "is_active"]
        if options["reset_password"]:
            user.set_password(password)
            fields.append("password")
        user.save(update_fields=fields)
        self.stdout.write(f"Администратор платформы {email} обновлён.")
