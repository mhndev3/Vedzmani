from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_admin_audit_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="adminauditevent",
            name="details",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
