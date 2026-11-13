import uuid

from django.db import models

from crm.accounts.models import User


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("Название компании", max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Владелец"
        ADMIN = "admin", "Администратор"
        LEAD = "lead", "Руководитель"
        MANAGER = "manager", "Менеджер"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="crm_unique_membership"
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["owner", "admin", "lead", "manager"]),
                name="crm_valid_role",
            ),
            # Один действующий владелец: передача владения меняет роли в транзакции.
            models.UniqueConstraint(
                fields=["organization"],
                condition=models.Q(role="owner", is_active=True),
                name="crm_single_active_owner",
            ),
        ]


class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="branches"
    )
    name = models.CharField("Название филиала", max_length=160)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="crm_unique_branch_name"
            )
        ]


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.Role.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(User, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["admin", "lead", "manager"]),
                name="crm_invite_non_owner",
            ),
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=models.Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name="crm_unique_pending_invite",
            ),
        ]


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="audit_events"
    )
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    target_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
