from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("orders", "0002_order_delivery_details_payment_status")]
    operations = [
        migrations.AlterField(model_name="order", name="status", field=models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed")], default="pending", max_length=20)),
        migrations.AlterField(model_name="order", name="payment_status", field=models.CharField(choices=[("unpaid", "Unpaid"), ("paid", "Paid"), ("failed", "Failed")], default="unpaid", max_length=20)),
        migrations.CreateModel(name="SepPaymentAttempt", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("res_num", models.CharField(max_length=40, unique=True)),
            ("token", models.CharField(blank=True, default="", max_length=100)),
            ("ref_num", models.CharField(blank=True, max_length=80, null=True, unique=True)),
            ("shipping_amount_toman", models.PositiveBigIntegerField()),
            ("amount_rial", models.PositiveBigIntegerField()),
            ("status", models.CharField(choices=[("initiating", "Initiating"), ("pending", "Pending"), ("paid", "Paid"), ("out_of_stock", "Out of stock"), ("failed", "Failed"), ("reversed", "Reversed")], default="initiating", max_length=20)),
            ("provider_result_code", models.IntegerField(blank=True, null=True)),
            ("provider_rrn", models.CharField(blank=True, default="", max_length=40)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sep_payment_attempts", to="orders.order")),
        ], options={"ordering": ["-created_at", "-id"]}),
        migrations.AddIndex(model_name="seppaymentattempt", index=models.Index(fields=["order", "-created_at"], name="sep_pay_order_created_idx")),
    ]
