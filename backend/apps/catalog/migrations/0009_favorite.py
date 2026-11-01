from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_variant_image_responsive_keys"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Favorite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorited_by", to="catalog.product")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorite_products", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["user", "-created_at"], name="favorite_user_created_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="favorite",
            constraint=models.UniqueConstraint(fields=("user", "product"), name="catalog_favorite_user_product_uniq"),
        ),
    ]
