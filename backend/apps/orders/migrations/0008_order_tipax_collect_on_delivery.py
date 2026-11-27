# Snapshot the V1 shipping carrier and collection policy on every order.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_torobpay_payment_attempt"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="shipping_provider",
            field=models.CharField(
                choices=[("tipax", "Tipax")],
                default="tipax",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_payment",
            field=models.CharField(
                choices=[("collect_on_delivery", "Collect on delivery")],
                default="collect_on_delivery",
                max_length=24,
            ),
        ),
    ]
