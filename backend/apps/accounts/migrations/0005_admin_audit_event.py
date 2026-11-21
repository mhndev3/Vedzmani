from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_support_tickets"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("post", "POST"), ("put", "PUT"), ("patch", "PATCH"), ("delete", "DELETE")], max_length=8)),
                ("method", models.CharField(max_length=8)),
                ("path", models.CharField(max_length=255)),
                ("entity_type", models.CharField(max_length=80)),
                ("entity_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("response_status", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admin_audit_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(model_name="adminauditevent", index=models.Index(fields=["actor", "-created_at"], name="admin_audit_actor_time_idx")),
        migrations.AddIndex(model_name="adminauditevent", index=models.Index(fields=["entity_type", "-created_at"], name="admin_audit_entity_time_idx")),
        migrations.AddIndex(model_name="adminauditevent", index=models.Index(fields=["action", "-created_at"], name="admin_audit_action_time_idx")),
    ]
