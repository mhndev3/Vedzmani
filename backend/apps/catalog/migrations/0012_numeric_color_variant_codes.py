import random

from django.core.validators import RegexValidator
from django.db import migrations, models


def assign_numeric_card_codes(apps, schema_editor):
    ColorVariant = apps.get_model("catalog", "ColorVariant")
    Counter = apps.get_model("catalog", "ColorVariantCodeCounter")
    db = schema_editor.connection.alias

    variants = list(ColorVariant.objects.using(db).order_by("id"))
    # Clear legacy values first so no old manually-entered numeric code can collide.
    ColorVariant.objects.using(db).all().update(product_code=None)

    random.Random("vedzmani-card-codes-v1").shuffle(variants)
    for number, variant in enumerate(variants, start=1):
        ColorVariant.objects.using(db).filter(pk=variant.pk).update(
            product_code=str(number).zfill(2)
        )

    Counter.objects.using(db).update_or_create(
        pk=1,
        defaults={"next_value": len(variants) + 1},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0011_color_variant_product_codes"),
    ]

    operations = [
        migrations.CreateModel(
            name="ColorVariantCodeCounter",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("next_value", models.PositiveIntegerField(default=1)),
            ],
        ),
        migrations.RunPython(assign_numeric_card_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="colorvariant",
            name="product_code",
            field=models.CharField(
                blank=True,
                max_length=12,
                null=True,
                unique=True,
                validators=[
                    RegexValidator(
                        regex="^\\d+$",
                        message="کد کارت باید فقط شامل عدد باشد.",
                    )
                ],
                verbose_name="کد کارت محصول",
            ),
        ),

    ]
