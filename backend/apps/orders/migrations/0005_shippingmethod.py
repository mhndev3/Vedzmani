# Hand-written migration for the managed shipping-method configuration.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_alter_seppaymentattempt_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShippingMethod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("provider", models.CharField(choices=[("post", "Post"), ("tipax", "Tipax"), ("other", "Other")], default="other", max_length=12)),
                ("pricing_mode", models.CharField(choices=[("fixed", "Fixed tariff"), ("quote", "Carrier quote required")], default="quote", max_length=10)),
                ("amount_toman", models.PositiveBigIntegerField(blank=True, null=True)),
                ("service_area", models.CharField(blank=True, default="", max_length=160)),
                ("min_delivery_days", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("max_delivery_days", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("description", models.CharField(blank=True, default="", max_length=500)),
                ("is_active", models.BooleanField(default=False)),
                ("position", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="shippingmethod",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("pricing_mode", "quote"), ("amount_toman__isnull", True))
                    | models.Q(("pricing_mode", "fixed"), ("amount_toman__isnull", False))
                ),
                name="shipping_method_pricing_amount_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="shippingmethod",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("min_delivery_days__isnull", True))
                    | models.Q(("max_delivery_days__isnull", True))
                    | models.Q(("max_delivery_days__gte", models.F("min_delivery_days")))
                ),
                name="shipping_method_delivery_days_ordered",
            ),
        ),
    ]
