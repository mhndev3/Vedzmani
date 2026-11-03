from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0012_numeric_color_variant_codes"),
    ]

    operations = [
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
                        regex=r"^\d+$",
                        message="کد کارت باید فقط شامل عدد باشد.",
                    )
                ],
                verbose_name="کد کارت محصول",
            ),
        ),
    ]
