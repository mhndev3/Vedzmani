# Generated for immutable homepage section revisions.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0016_storefront_theme"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HomepageSectionRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("snapshot", models.JSONField()),
                ("action", models.CharField(choices=[("created", "Created"), ("updated", "Updated"), ("rollback", "Rollback")], max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="homepage_section_revisions", to=settings.AUTH_USER_MODEL)),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="catalog.homepagesection")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["section", "-created_at"], name="home_section_rev_idx")],
            },
        ),
    ]
