# Generated for the customer support ticket workspace.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0003_otp_purposes"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(max_length=160)),
                ("category", models.CharField(choices=[("order", "Order"), ("shipping", "Shipping"), ("product", "Product"), ("payment", "Payment"), ("other", "Other")], default="other", max_length=20)),
                ("status", models.CharField(choices=[("open", "Open"), ("in_progress", "In progress"), ("waiting_customer", "Waiting for customer"), ("resolved", "Resolved"), ("closed", "Closed")], default="open", max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_tickets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
        migrations.CreateModel(
            name="SupportTicketMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField(max_length=5000)),
                ("is_internal", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="support_messages", to=settings.AUTH_USER_MODEL)),
                ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="accounts.supportticket")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="supportticket",
            index=models.Index(fields=["status", "-updated_at"], name="support_status_updated_idx"),
        ),
        migrations.AddIndex(
            model_name="supportticketmessage",
            index=models.Index(fields=["ticket", "created_at"], name="support_msg_ticket_created_idx"),
        ),
    ]
