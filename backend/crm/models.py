import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        user = self.model(email=email.strip().lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    name = models.CharField("Имя", max_length=120)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]
    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="crm_unique_email_ci")
        ]


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
        ]


class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="branches"
    )
    name = models.CharField("Название филиала", max_length=160)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="crm_unique_branch_name"
            )
        ]


class Registration(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    company_name = models.CharField(max_length=160)
    password_hash = models.CharField(max_length=128)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


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


class RateLimitBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)


class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    name = models.CharField("ФИО клиента", max_length=240)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    city = models.CharField("Город", max_length=120, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RelatedContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="contacts"
    )
    name = models.CharField(max_length=240)
    relationship = models.CharField(max_length=80)
    phone = models.CharField(max_length=40, blank=True)


class Lead(models.Model):
    class Stage(models.TextChoices):
        NEW = "new", "Новое"
        WORK = "work", "В работе"
        CONSULTATION = "consultation", "Консультация"
        EXPECTED = "expected", "Ожидаем поступление"
        ADMITTED = "admitted", "Поступил"
        REFUSED = "refused", "Отказ"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="leads")
    assignee = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="leads"
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    title = models.CharField(max_length=240)
    source = models.CharField(max_length=120, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.NEW)
    refusal_reason = models.CharField(max_length=500, blank=True)
    next_contact_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    stage__in=[
                        "new",
                        "work",
                        "consultation",
                        "expected",
                        "admitted",
                        "refused",
                    ]
                ),
                name="crm_valid_lead_stage",
            ),
            models.CheckConstraint(
                condition=~models.Q(stage="refused") | ~models.Q(refusal_reason=""),
                name="crm_refusal_requires_reason",
            ),
        ]
        indexes = [models.Index(fields=["organization", "stage", "-updated_at"])]


class LeadActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class FollowUpTask(models.Model):
    """Задача наследует компанию и ответственного от обращения."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="follow_up_tasks"
    )
    title = models.CharField("Задача", max_length=240)
    due_at = models.DateTimeField("Срок", db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    completed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class RehubCenter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    domain = models.CharField(max_length=253)
    encrypted_key = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "domain"], name="crm_unique_center_domain"
            )
        ]


class AdmissionTransfer(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "В очереди"
        SENDING = "sending", "Отправляется"
        RETRY = "retry", "Ожидает повтора"
        DELIVERED = "delivered", "Доставлено"
        BLOCKED = "blocked", "Подключение требует внимания"
        FAILED = "failed", "Ошибка передачи"
        CONFLICT = "conflict", "Конфликт данных"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="transfers")
    center = models.ForeignKey(RehubCenter, on_delete=models.PROTECT)
    payload = models.JSONField()
    confirmed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    attempt_count = models.PositiveIntegerField(default=0)
    cycle_attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_until = models.DateTimeField(null=True)
    lease_id = models.UUIDField(null=True)
    resident_id = models.CharField(max_length=100, blank=True)
    last_error = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "center"], name="crm_unique_admission_transfer"
            )
        ]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]


class DeliveryAttempt(models.Model):
    transfer = models.ForeignKey(
        AdmissionTransfer, on_delete=models.CASCADE, related_name="attempts"
    )
    number = models.PositiveIntegerField()
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    outcome = models.CharField(max_length=120, default="unknown")
    http_status = models.PositiveIntegerField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transfer", "number"], name="crm_unique_attempt"
            )
        ]
