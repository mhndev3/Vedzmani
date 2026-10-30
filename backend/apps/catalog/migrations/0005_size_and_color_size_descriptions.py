# Generated for flexible product-size and exact color-size descriptions.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_seed_knitwear_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductSizeDescription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.TextField()),
                ("product", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="size_descriptions",
                    to="catalog.product",
                )),
                ("size", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="product_descriptions",
                    to="catalog.size",
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="productsizedescription",
            constraint=models.UniqueConstraint(
                fields=("product", "size"),
                name="product_size_description_unique",
            ),
        ),
        migrations.CreateModel(
            name="VariantSizeDescription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.TextField()),
                ("variant_size", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="description",
                    to="catalog.variantsize",
                )),
            ],
        ),
    ]
