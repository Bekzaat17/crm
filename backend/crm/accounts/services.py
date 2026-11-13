"""Регистрация, подтверждение почты и восстановление пароля."""

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from crm.core.errors import ApiError
from crm.core.mail import Mailer, default_mailer
from crm.core.throttle import throttle
from crm.core.tokens import digest, new_token
from crm.core.validation import clean_email, clean_text
from crm.organizations.services import create_organization

from .emails import password_reset_email, registration_email
from .models import Registration, User
from .passwords import check_password


def request_registration(data, mailer: Mailer | None = None):
    email = clean_email(data.get("email"))
    name = clean_text(data.get("name"), "Ваше имя", 120)
    company_name = clean_text(data.get("company_name"), "Название компании", 160)
    password = check_password(data.get("password"), email, name)
    throttle("registration-email", email, 3)
    if User.objects.filter(email__iexact=email).exists():
        return
    token = new_token()
    Registration.objects.update_or_create(
        email=email,
        defaults={
            "name": name,
            "company_name": company_name,
            "password_hash": make_password(password),
            "token_hash": digest(token),
            "expires_at": timezone.now() + timedelta(hours=24),
        },
    )
    (mailer or default_mailer()).send(registration_email(email, token))


@transaction.atomic
def confirm_registration(token):
    registration = (
        Registration.objects.select_for_update()
        .filter(token_hash=digest(token), expires_at__gt=timezone.now())
        .first()
    )
    if (
        not registration
        or User.objects.filter(email__iexact=registration.email).exists()
    ):
        raise ApiError(
            "Ссылка недействительна или уже использована. Зарегистрируйтесь заново."
        )
    user = User.objects.create(
        email=registration.email,
        name=registration.name,
        password=registration.password_hash,
    )
    create_organization(user, registration.company_name)
    registration.delete()
    return user


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
