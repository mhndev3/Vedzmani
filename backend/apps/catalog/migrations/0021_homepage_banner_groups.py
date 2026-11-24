# Group homepage banners into named sliders and preserve existing banners.
from django.db import migrations, models
import django.db.models.deletion


def assign_default_group(apps, schema_editor):
    Group = apps.get_model("catalog", "HomepageBannerGroup")
    Banner = apps.get_model("catalog", "HomepageBanner")
    group, _ = Group.objects.get_or_create(
        slug="main",
        defaults={"name": "بنرهای اصلی", "position": 0, "is_active": True},
    )
    Banner.objects.filter(group__isnull=True).update(group_id=group.pk)


def unassign_default_group(apps, schema_editor):
    Banner = apps.get_model("catalog", "HomepageBanner")
    Banner.objects.update(group=None)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0020_category_product_fields")]

    operations = [
        migrations.CreateModel(
            name="HomepageBannerGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddField(
            model_name="homepagebanner",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="banners",
                to="catalog.homepagebannergroup",
            ),
        ),
        migrations.RunPython(assign_default_group, unassign_default_group),
        migrations.AlterField(
            model_name="homepagebanner",
            name="group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="banners",
                to="catalog.homepagebannergroup",
            ),
        ),
    ]
