from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0003_sep_payment_attempt"),
    ]

    operations = [
        migrations.AlterField(
            model_name="seppaymentattempt",
            name="status",
            field=models.CharField(
                choices=[
                    ("initiating", "Initiating"),
                    ("pending", "Pending"),
                    ("paid", "Paid"),
                    ("out_of_stock", "Out of stock"),
                    ("reversal_pending", "Reversal pending"),
                    ("failed", "Failed"),
                    ("reversed", "Reversed"),
                ],
                default="initiating",
                max_length=20,
            ),
        ),
    ]
