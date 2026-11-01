# Per-color + size measurements (needed for products whose colors have different measurements).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0005_size_and_color_size_descriptions"),
    ]

    operations = [
        migrations.CreateModel(
            name="VariantSizeMeasurement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("value", models.CharField(max_length=80)),
                ("unit", models.CharField(blank=True, max_length=30)),
                ("position", models.PositiveIntegerField(default=0)),
                (
                    "variant_size",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="measurements",
                        to="catalog.variantsize",
                    ),
                ),
            ],
            options={
                "ordering": ["position", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="variantsizemeasurement",
            constraint=models.UniqueConstraint(
                fields=("variant_size", "position"),
                name="variant_size_measurement_unique_position",
            ),
        ),
    ]
