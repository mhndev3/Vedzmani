# Generated for immutable homepage section revisions.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_homepage_section_baselines(apps, schema_editor):
    HomepageSection = apps.get_model("catalog", "HomepageSection")
    HomepageSectionRevision = apps.get_model("catalog", "HomepageSectionRevision")
    database = schema_editor.connection.alias
    for section in HomepageSection.objects.using(database).all().iterator():
        snapshot = {
            "title": section.title,
            "eyebrow": section.eyebrow,
            "section_type": section.section_type,
            "status": section.status,
            "position": section.position,
            "item_limit": section.item_limit,
            "show_view_all": section.show_view_all,
            "view_all_url": section.view_all_url,
            "categories": list(section.categories.using(database).values_list("id", flat=True)),
            "products": list(section.products.using(database).values_list("id", flat=True)),
        }
        HomepageSectionRevision.objects.using(database).create(
            section_id=section.pk, snapshot=snapshot, action="baseline", created_by_id=None,
        )



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
                ("action", models.CharField(choices=[("baseline", "Baseline"), ("created", "Created"), ("updated", "Updated"), ("rollback", "Rollback")], max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="homepage_section_revisions", to=settings.AUTH_USER_MODEL)),
                ("section", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="catalog.homepagesection")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["section", "-created_at"], name="home_section_rev_idx")],
            },
        ),
        migrations.RunPython(seed_homepage_section_baselines, migrations.RunPython.noop),
    ]
