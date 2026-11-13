import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Отдельная миграция: изменение схемы после переноса данных в 0005."""

    dependencies = [("crm", "0005_pipelinestage")]

    operations = [
        migrations.RemoveIndex(model_name="lead", name="crm_lead_organiz_f95cbe_idx"),
        migrations.RemoveConstraint(model_name="lead", name="crm_valid_lead_stage"),
        migrations.RemoveConstraint(
            model_name="lead", name="crm_refusal_requires_reason"
        ),
        migrations.RemoveField(model_name="lead", name="stage"),
        migrations.RenameField(
            model_name="lead", old_name="stage_ref", new_name="stage"
        ),
        migrations.AlterField(
            model_name="lead",
            name="stage",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="leads",
                to="crm.pipelinestage",
            ),
        ),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(
                fields=["organization", "stage", "-updated_at"],
                name="crm_lead_organiz_bf75f4_idx",
            ),
        ),
    ]
