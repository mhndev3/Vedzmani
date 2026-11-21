# Persist the provider payment page for safe retries of the same active attempt.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_torobpay_payment_attempt"),
    ]

    operations = [
        migrations.AddField(
            model_name="torobpaypaymentattempt",
            name="payment_page_url",
            field=models.URLField(blank=True, default="", max_length=2048),
        ),
    ]
