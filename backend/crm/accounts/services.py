"""Восстановление пароля. Аккаунты создаются приглашением в компанию."""

from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction

from crm.core.errors import ApiError
from crm.core.mail import Mailer, default_mailer
from crm.core.throttle import throttle
from crm.core.validation import clean_email, clean_text

from .emails import password_reset_email
from .models import User
from .passwords import check_password


def request_password_reset(email, mailer: Mailer | None = None):
    email = clean_email(email)
    throttle("reset-email", email, 3)
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user:
        token = default_token_generator.make_token(user)
        (mailer or default_mailer()).send(password_reset_email(user, token))


@transaction.atomic
def reset_password(data):
    token = clean_text(data.get("token"), "Код восстановления", 256)
    uid = clean_text(data.get("uid"), "Аккаунт", 64)
    try:
        user = User.objects.select_for_update().filter(pk=uid, is_active=True).first()
    except (ValidationError, ValueError, TypeError):
        user = None
    if not user or not default_token_generator.check_token(user, token):
        raise ApiError("Ссылка недействительна или срок её действия истёк.")
    user.set_password(check_password(data.get("password"), user.email, user.name))
    user.save(update_fields=["password"])
