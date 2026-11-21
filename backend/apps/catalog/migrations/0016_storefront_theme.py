# Generated for the storefront theme studio.
import django.db.models.deletion
import apps.catalog.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0015_homepage_banner"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StorefrontTheme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("draft_settings", models.JSONField(default=apps.catalog.models.default_storefront_theme_settings)),
                ("published_settings", models.JSONField(default=apps.catalog.models.default_storefront_theme_settings)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "storefront theme",
                "verbose_name_plural": "storefront theme",
            },
        ),
    ]
