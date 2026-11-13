import uuid

import django.db.models.deletion
from django.db import migrations, models

# Этапы по умолчанию совпадают с прежним списком: обращения переносятся по коду.
DEFAULT_STAGES = [
    ("new", "Новое", "open"),
    ("work", "В работе", "open"),
    ("consultation", "Консультация", "open"),
    ("expected", "Ожидаем поступление", "open"),
    ("admitted", "Поступил", "admitted"),
    ("refused", "Отказ", "refused"),
]


def create_default_stages(apps, schema_editor):
    Organization = apps.get_model("crm", "Organization")
    PipelineStage = apps.get_model("crm", "PipelineStage")
    Lead = apps.get_model("crm", "Lead")
    for organization in Organization.objects.all():
        for position, (code, name, kind) in enumerate(DEFAULT_STAGES):
            stage = PipelineStage.objects.create(
                organization=organization, name=name, kind=kind, position=position
            )
            Lead.objects.filter(organization=organization, stage=code).update(
                stage_ref=stage
            )


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0004_rehubcenter_admissiontransfer_deliveryattempt_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PipelineStage",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=80, verbose_name="Название этапа"),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("open", "В работе"),
                            ("admitted", "Поступил"),
                            ("refused", "Отказ"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("color", models.CharField(blank=True, max_length=7)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pipeline_stages",
                        to="crm.organization",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["organization", "is_active", "position"],
                        name="crm_pipelin_organiz_6582bc_idx",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(kind__in=["open", "admitted", "refused"]),
                        name="crm_valid_stage_kind",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(is_active=True),
                        fields=("organization", "name"),
                        name="crm_unique_active_stage_name",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="lead",
            name="stage_ref",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="crm.pipelinestage",
            ),
        ),
        migrations.RunPython(create_default_stages, migrations.RunPython.noop),
    ]
