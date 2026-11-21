# TorobPay payment-attempt persistence; credentials and callback bodies are never stored.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_shippingmethod"),
    ]

    operations = [
        migrations.CreateModel(
            name="TorobPayPaymentAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("merchant_transaction_id", models.UUIDField(unique=True)),
                ("payment_token", models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ("provider_transaction_id", models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ("amount_toman", models.PositiveBigIntegerField()),
                ("amount_rial", models.PositiveBigIntegerField()),
                ("status", models.CharField(
                    choices=[
                        ("initiating", "Initiating"),
                        ("new", "New"),
                        ("ipg", "IPG"),
                        ("verify_for_w", "Verify for merchant"),
                        ("settle_for_w", "Settle for merchant"),
                        ("ongoing", "Ongoing"),
                        ("failed", "Failed"),
                        ("canceled", "Canceled"),
                        ("out_of_stock", "Out of stock"),
                        ("reversal_pending", "Reversal pending"),
                    ],
                    default="initiating",
                    max_length=24,
                )),
                ("return_state", models.CharField(blank=True, default="", max_length=16)),
                ("provider_status", models.CharField(blank=True, default="", max_length=32)),
                ("last_error_code", models.CharField(blank=True, default="", max_length=64)),
                ("callback_received_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="torobpay_payment_attempts",
                    to="orders.order",
                )),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="torobpaypaymentattempt",
            index=models.Index(fields=["order", "-created_at"], name="torob_pay_order_created_idx"),
        ),
        migrations.AddIndex(
            model_name="torobpaypaymentattempt",
            index=models.Index(fields=["status", "created_at"], name="torob_pay_status_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="torobpaypaymentattempt",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount_toman__gt", 0)),
                name="torobpay_amount_toman_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="torobpaypaymentattempt",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount_rial__gt", 0)),
                name="torobpay_amount_rial_positive",
            ),
        ),
    ]
