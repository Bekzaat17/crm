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
