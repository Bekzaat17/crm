import uuid

from django.db import models

from crm.accounts.models import User
from crm.organizations.models import Branch, Membership, Organization


class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    name = models.CharField("ФИО клиента", max_length=240)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    # Только цифры: поиск клиента по номеру собеседника в мессенджере.
    phone_digits = models.CharField(max_length=20, blank=True, db_index=True)
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
    phone_digits = models.CharField(max_length=20, blank=True, db_index=True)
    version = models.PositiveIntegerField(default=1)


class PipelineStage(models.Model):
    """Настраиваемый этап воронки компании.

    Название и порядок задаёт компания; бизнес-правила опираются только на тип:
    открытый этап, поступление или отказ.
    """

    class Kind(models.TextChoices):
        OPEN = "open", "В работе"
        ADMITTED = "admitted", "Поступил"
        REFUSED = "refused", "Отказ"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="pipeline_stages"
    )
    name = models.CharField("Название этапа", max_length=80)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OPEN)
    color = models.CharField(max_length=7, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=["open", "admitted", "refused"]),
                name="crm_valid_stage_kind",
            ),
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=models.Q(is_active=True),
                name="crm_unique_active_stage_name",
            ),
        ]
        indexes = [models.Index(fields=["organization", "is_active", "position"])]

    @property
    def is_closed(self):
        return self.kind != self.Kind.OPEN


class Lead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="leads")
    assignee = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="leads"
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    stage = models.ForeignKey(
        PipelineStage, on_delete=models.PROTECT, related_name="leads"
    )
    title = models.CharField(max_length=240)
    source = models.CharField(max_length=120, blank=True)
    refusal_reason = models.CharField(max_length=500, blank=True)
    next_contact_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "stage", "-updated_at"])]


class LeadActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
