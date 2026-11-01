# Generated for idempotent guest-cart transfer.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GuestCartMerge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField()),
                ("payload_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="guest_cart_merges", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="guestcartmerge",
            constraint=models.UniqueConstraint(fields=("user", "token"), name="guestcartmerge_user_token_uniq"),
        ),
        migrations.AddIndex(
            model_name="guestcartmerge",
            index=models.Index(fields=["user", "-created_at"], name="guestmerge_user_created_idx"),
        ),
    ]
