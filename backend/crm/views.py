import logging

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone

from . import services
from .http import endpoint
from .models import AuditEvent, Invitation, Membership

logger = logging.getLogger(__name__)


def csrf_failure(request, reason=""):
    return JsonResponse(
        {"error": "Защита сессии: обновите страницу и повторите действие."}, status=403
    )


def user_json(user):
    return {"id": str(user.id), "email": user.email, "name": user.name}


def memberships_json(user):
    return [
        {
            "id": str(m.organization_id),
            "name": m.organization.name,
            "role": m.role,
            "role_label": m.get_role_display(),
        }
        for m in user.memberships.filter(is_active=True)
        .select_related("organization")
        .order_by("organization__name", "organization_id")
    ]


def auth_response(request):
    return JsonResponse(
        {
            "user": user_json(request.user) if request.user.is_authenticated else None,
            "organizations": memberships_json(request.user)
            if request.user.is_authenticated
            else [],
            "csrf_token": get_token(request),
        }
    )


@endpoint(["GET"])
def session(request):
    return auth_response(request)


def auth_throttle(request, scope, limit=20):
    services.throttle(scope, request.META.get("REMOTE_ADDR", "unknown"), limit, 900)


@endpoint(["POST"])
def register(request):
    auth_throttle(request, "register-ip", 10)
    services.request_registration(request.payload)
    return JsonResponse(
        {
            "message": "Если адрес доступен для регистрации, мы отправили письмо. Проверьте почту. Если аккаунт уже есть — войдите."
        },
        status=202,
    )


@endpoint(["POST"])
def verify(request):
    auth_throttle(request, "verify-ip", 30)
    token = services.clean_text(request.payload.get("token"), "Код подтверждения", 256)
    user = services.confirm_registration(token)
    login(request, user)
    return auth_response(request)


@endpoint(["POST"])
def sign_in(request):
    auth_throttle(request, "login-ip", 60)
    email = services.clean_email(request.payload.get("email"))
    services.throttle("login-email", email, 10, 900)
    password = request.payload.get("password")
    if not isinstance(password, str) or len(password) > 128:
        raise services.ApiError("Неверная почта или пароль.", 401)
    user = authenticate(request, email=email, password=password)
    if not user:
        raise services.ApiError("Неверная почта или пароль.", 401)
    login(request, user)
    return auth_response(request)


@endpoint(["POST"], authenticated=True)
def sign_out(request):
    logout(request)
    return JsonResponse({"message": "Вы вышли из аккаунта."})


@endpoint(["POST"])
def forgot_password(request):
    auth_throttle(request, "reset-ip", 15)
    services.request_password_reset(request.payload.get("email"))
    return JsonResponse(
        {"message": "Если аккаунт существует, письмо для восстановления отправлено."},
        status=202,
    )


@endpoint(["POST"])
def reset_password(request):
    auth_throttle(request, "reset-confirm-ip", 20)
    services.reset_password(request.payload)
    return JsonResponse({"message": "Пароль изменён. Войдите с новым паролем."})


@endpoint(["GET"], authenticated=True)
def organization(request, organization_id):
    membership = services.get_membership(request.user, organization_id)
    org = membership.organization
    return JsonResponse(
        {
            "id": str(org.id),
            "name": org.name,
            "role": membership.role,
            "role_label": membership.get_role_display(),
            "can_manage_team": membership.role
            in (Membership.Role.OWNER, Membership.Role.ADMIN),
            "branches": [
                {"id": str(b.id), "name": b.name} for b in org.branches.order_by("name")
            ],
            "member_count": org.memberships.filter(is_active=True).count(),
            "created_at": org.created_at.isoformat(),
        }
    )


@endpoint(["GET"], authenticated=True)
def team(request, organization_id):
    services.require_team_admin(services.get_membership(request.user, organization_id))
    members = (
        Membership.objects.filter(organization_id=organization_id)
        .select_related("user")
        .order_by("created_at")
    )
    invitations = Invitation.objects.filter(organization_id=organization_id).order_by(
        "-created_at"
    )[:100]
    now = timezone.now()
    return JsonResponse(
        {
            "members": [
                {
                    "id": str(m.id),
                    "user_id": str(m.user_id),
                    "name": m.user.name,
                    "email": m.user.email,
                    "role": m.role,
                    "role_label": m.get_role_display(),
                    "is_active": m.is_active,
                }
                for m in members
            ],
            "invitations": [
                {
                    "id": str(i.id),
                    "email": i.email,
                    "role": i.role,
                    "role_label": i.get_role_display(),
                    "created_at": i.created_at.isoformat(),
                    "expires_at": i.expires_at.isoformat(),
                    "status": "accepted"
                    if i.accepted_at
                    else "revoked"
                    if i.revoked_at
                    else "expired"
                    if i.expires_at <= now
                    else "pending",
                }
                for i in invitations
            ],
        }
    )


@endpoint(["POST"], authenticated=True)
def create_invitation(request, organization_id):
    # Проверяем компанию до ограничения частоты, чтобы чужие UUID не расходовали квоту.
    services.require_team_admin(services.get_membership(request.user, organization_id))
    services.throttle("invite-company", str(organization_id), 30)
    invitation = services.invite_member(request.user, organization_id, request.payload)
    return JsonResponse(
        {
            "id": str(invitation.id),
            "message": "Приглашение отправлено на почту сотрудника.",
        },
        status=201,
    )


@endpoint(["POST"])
def invitation_preview(request):
    auth_throttle(request, "invite-preview", 60)
    token = services.clean_text(request.payload.get("token"), "Приглашение", 256)
    invitation = services.available_invitation(token)
    return JsonResponse(
        {
            "company_name": invitation.organization.name,
            "email": invitation.email,
            "role_label": invitation.get_role_display(),
            "expires_at": invitation.expires_at.isoformat(),
        }
    )


@endpoint(["POST"])
def accept_invitation(request):
    auth_throttle(request, "invite-accept", 20)
    token = services.clean_text(request.payload.get("token"), "Приглашение", 256)
    user, organization_id = services.accept_invitation(
        token, request.user, request.payload
    )
    login(request, user)
    response = {
        "user": user_json(user),
        "organizations": memberships_json(user),
        "organization_id": str(organization_id),
        "csrf_token": get_token(request),
    }
    return JsonResponse(response)


@endpoint(["POST"], authenticated=True)
def revoke_invitation(request, organization_id, invitation_id):
    services.revoke_invitation(request.user, organization_id, invitation_id)
    return JsonResponse({"message": "Приглашение отозвано."})


@endpoint(["POST"], authenticated=True)
def deactivate_member(request, organization_id, membership_id):
    services.deactivate_member(request.user, organization_id, membership_id)
    return JsonResponse({"message": "Доступ сотрудника отключён."})


@endpoint(["GET"], authenticated=True)
def audit(request, organization_id):
    services.require_team_admin(services.get_membership(request.user, organization_id))
    labels = {
        "organization.created": "Создана компания",
        "invitation.created": "Отправлено приглашение",
        "invitation.accepted": "Сотрудник принял приглашение",
        "invitation.revoked": "Приглашение отозвано",
        "membership.deactivated": "Отключён доступ сотрудника",
    }
    events = (
        AuditEvent.objects.filter(organization_id=organization_id)
        .select_related("actor")
        .order_by("-created_at")[:50]
    )
    return JsonResponse(
        {
            "events": [
                {
                    "id": str(e.id),
                    "action": labels.get(e.action, e.action),
                    "actor": e.actor.name,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ]
        }
    )
