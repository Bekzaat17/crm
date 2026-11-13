import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .models import (
    AuditEvent,
    Branch,
    Invitation,
    Membership,
    Organization,
    RateLimitBucket,
    Registration,
    User,
)


class ApiError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def clean_text(value, label, max_length):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_length
    ):
        raise ApiError(f"Заполните поле «{label}» (не более {max_length} символов).")
    return value.strip()


def clean_email(value):
    email = clean_text(value, "Электронная почта", 254).lower()
    try:
        validate_email(email)
    except ValidationError:
        raise ApiError("Укажите корректный адрес электронной почты.")
    return email


def check_password(value, email, name):
    if not isinstance(value, str) or len(value) > 128:
        raise ApiError("Пароль должен содержать от 10 до 128 символов.")
    try:
        validate_password(value, User(email=email, name=name, first_name=name))
    except ValidationError as exc:
        raise ApiError(" ".join(exc.messages))
    return value


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def throttle(scope, identity, limit, seconds=3600):
    # Счётчик общий для процессов приложения; адрес прокси из заголовков не доверяем.
    now = timezone.now()
    key = digest(f"{scope}:{identity}")
    with transaction.atomic():
        bucket, _ = RateLimitBucket.objects.get_or_create(
            key=key, defaults={"started_at": now}
        )
        bucket = RateLimitBucket.objects.select_for_update().get(pk=bucket.pk)
        if bucket.started_at <= now - timedelta(seconds=seconds):
            bucket.started_at, bucket.count = now, 0
        if bucket.count >= limit:
            raise ApiError("Слишком много попыток. Попробуйте позже.", 429)
        bucket.count += 1
        bucket.save(update_fields=["started_at", "count"])


def send_link(email, subject, message, page, **params):
    # Фрагмент URL не передаётся серверу в запросе и не попадает в access log.
    url = f"{settings.FRONTEND_URL}/{page}#{urlencode(params)}"
    send_mail(
        subject,
        f"{message}\n\n{url}\n\nЕсли вы не запрашивали это письмо, проигнорируйте его.",
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )


def request_registration(data):
    email = clean_email(data.get("email"))
    name = clean_text(data.get("name"), "Ваше имя", 120)
    company_name = clean_text(data.get("company_name"), "Название компании", 160)
    password = check_password(data.get("password"), email, name)
    throttle("registration-email", email, 3)
    if User.objects.filter(email__iexact=email).exists():
        return
    token = secrets.token_urlsafe(32)
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
    send_link(
        email,
        "Подтвердите регистрацию RehubPro CRM",
        "Подтвердите почту, чтобы создать компанию. Ссылка действует 24 часа.",
        "verify",
        token=token,
    )


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
    organization = Organization.objects.create(name=registration.company_name)
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.OWNER
    )
    Branch.objects.create(organization=organization, name="Основной центр")
    AuditEvent.objects.create(
        organization=organization,
        actor=user,
        action="organization.created",
        target_id=str(organization.id),
    )
    registration.delete()
    return user


def get_membership(user, organization_id):
    membership = (
        Membership.objects.select_related("organization")
        .filter(
            user=user,
            organization_id=organization_id,
            is_active=True,
        )
        .first()
    )
    if not membership:
        raise ApiError("Компания не найдена или доступ закрыт.", 404)
    return membership


def require_team_admin(membership):
    if membership.role not in (Membership.Role.OWNER, Membership.Role.ADMIN):
        raise ApiError("Управлять командой может владелец или администратор.", 403)


@transaction.atomic
def invite_member(actor, organization_id, data):
    membership = get_membership(actor, organization_id)
    require_team_admin(membership)
    # Сериализуем создание/отзыв приглашений и изменение состава одной компании.
    organization = Organization.objects.select_for_update().get(pk=organization_id)
    email = clean_email(data.get("email"))
    role = data.get("role")
    if role not in (
        Membership.Role.ADMIN,
        Membership.Role.LEAD,
        Membership.Role.MANAGER,
    ):
        raise ApiError("Выберите роль администратора, руководителя или менеджера.")
    if Membership.objects.filter(
        organization=organization, user__email__iexact=email, is_active=True
    ).exists():
        raise ApiError("Этот сотрудник уже состоит в компании.", 409)
    now = timezone.now()
    existing = Invitation.objects.filter(
        organization=organization,
        email=email,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    )
    if existing.filter(expires_at__gt=now).exists():
        raise ApiError(
            "Приглашение уже отправлено. Сначала отзовите его для повторной отправки.",
            409,
        )
    existing.update(revoked_at=now)
    token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        organization=organization,
        email=email,
        role=role,
        invited_by=actor,
        token_hash=digest(token),
        expires_at=now + timedelta(days=7),
    )
    AuditEvent.objects.create(
        organization=organization,
        actor=actor,
        action="invitation.created",
        target_id=str(invitation.id),
    )
    # Письмо отправляется до commit: ошибка SMTP не оставляет активное несохранённое приглашение.
    send_link(
        email,
        f"Приглашение в {organization.name}",
        f"Вас приглашают в компанию «{organization.name}» в RehubPro CRM. Ссылка действует 7 дней.",
        "invite",
        token=token,
    )
    return invitation


def available_invitation(token, lock=False):
    queryset = Invitation.objects.select_related("organization")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    invitation = queryset.filter(
        token_hash=digest(token),
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if not invitation:
        raise ApiError(
            "Приглашение недействительно, отозвано или уже использовано.", 404
        )
    return invitation


@transaction.atomic
def accept_invitation(token, current_user, data):
    invitation = available_invitation(token, lock=True)
    if current_user.is_authenticated:
        if current_user.email.lower() != invitation.email:
            raise ApiError("Войдите с почтой, на которую отправлено приглашение.", 403)
        user = current_user
    else:
        if User.objects.filter(email__iexact=invitation.email).exists():
            raise ApiError(
                "Аккаунт с этой почтой уже есть. Сначала войдите в него.", 409
            )
        name = clean_text(data.get("name"), "Ваше имя", 120)
        password = check_password(data.get("password"), invitation.email, name)
        user = User.objects.create_user(
            email=invitation.email, password=password, name=name
        )
    membership, created = Membership.objects.get_or_create(
        organization=invitation.organization,
        user=user,
        defaults={"role": invitation.role},
    )
    if not created and not membership.is_active:
        membership.role, membership.is_active = invitation.role, True
        membership.save(update_fields=["role", "is_active"])
    # Существующему активному сотруднику приглашение не меняет роль.
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    AuditEvent.objects.create(
        organization=invitation.organization,
        actor=user,
        action="invitation.accepted",
        target_id=str(invitation.id),
    )
    return user, invitation.organization_id


@transaction.atomic
def revoke_invitation(actor, organization_id, invitation_id):
    require_team_admin(get_membership(actor, organization_id))
    invitation = (
        Invitation.objects.select_for_update()
        .filter(pk=invitation_id, organization_id=organization_id)
        .first()
    )
    if not invitation:
        raise ApiError("Приглашение не найдено.", 404)
    if invitation.accepted_at or invitation.revoked_at:
        raise ApiError("Приглашение уже закрыто.", 409)
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["revoked_at"])
    AuditEvent.objects.create(
        organization_id=organization_id,
        actor=actor,
        action="invitation.revoked",
        target_id=str(invitation.id),
    )


@transaction.atomic
def deactivate_member(actor, organization_id, membership_id):
    require_team_admin(get_membership(actor, organization_id))
    Organization.objects.select_for_update().get(pk=organization_id)
    target = (
        Membership.objects.select_for_update()
        .filter(pk=membership_id, organization_id=organization_id)
        .first()
    )
    if not target:
        raise ApiError("Сотрудник не найден.", 404)
    if target.role == Membership.Role.OWNER or target.user_id == actor.pk:
        raise ApiError(
            "Владельца и собственный доступ нельзя отключить через управление командой.",
            403,
        )
    target.is_active = False
    target.save(update_fields=["is_active"])
    AuditEvent.objects.create(
        organization_id=organization_id,
        actor=actor,
        action="membership.deactivated",
        target_id=str(target.id),
    )


def request_password_reset(email):
    email = clean_email(email)
    throttle("reset-email", email, 3)
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user:
        send_link(
            email,
            "Восстановление доступа RehubPro CRM",
            "Задайте новый пароль. Ссылка действует один час.",
            "reset",
            uid=str(user.id),
            token=default_token_generator.make_token(user),
        )


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
