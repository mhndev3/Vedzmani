# Generated for the homepage banner management workflow.
from django.db import migrations, models

import apps.catalog.models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0014_homepage_section")]

    operations = [
        migrations.CreateModel(
            name="HomepageBanner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, max_length=120)),
                ("subtitle", models.CharField(blank=True, max_length=240)),
                ("alt_text", models.CharField(max_length=200)),
                ("desktop_image", models.ImageField(upload_to=apps.catalog.models.homepage_banner_upload_to)),
                ("mobile_image", models.ImageField(blank=True, upload_to=apps.catalog.models.homepage_banner_upload_to)),
                ("cta_label", models.CharField(blank=True, max_length=60)),
                ("cta_url", models.CharField(blank=True, max_length=240)),
                ("position", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published")], default="draft", max_length=12)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["position", "id"],
                "indexes": [models.Index(fields=["status", "position"], name="home_banner_status_pos_idx")],
            },
        ),
    ]
