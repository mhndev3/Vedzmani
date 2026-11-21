from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0013_alter_colorvariant_numeric_product_code")]

    operations = [
        migrations.CreateModel(
            name="HomepageSection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("eyebrow", models.CharField(blank=True, max_length=120)),
                ("section_type", models.CharField(choices=[("categories", "Category grid"), ("products", "Selected products"), ("newest_products", "Newest products")], max_length=24)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published")], default="draft", max_length=12)),
                ("position", models.PositiveIntegerField(default=0)),
                ("item_limit", models.PositiveSmallIntegerField(default=8)),
                ("show_view_all", models.BooleanField(default=True)),
                ("view_all_url", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("categories", models.ManyToManyField(blank=True, related_name="homepage_sections", to="catalog.category")),
                ("products", models.ManyToManyField(blank=True, related_name="homepage_sections", to="catalog.product")),
            ],
            options={"ordering": ["position", "id"], "indexes": [models.Index(fields=["status", "position"], name="home_section_status_pos_idx")]},
        ),
    ]
