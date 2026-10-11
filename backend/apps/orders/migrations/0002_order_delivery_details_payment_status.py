# Hand-written (Django was not installable in the authoring environment, so `makemigrations` could not run).
# It must produce exactly the model state of apps/orders/models.py; CI's `makemigrations --check` verifies that.
#
# Safety for existing rows: every new column is NOT NULL with a constant default. On PostgreSQL 11+ that is a
# metadata-only change (no table rewrite), and pre-existing orders get blank delivery fields and `unpaid`.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='address',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AddField(
            model_name='order',
            name='city',
            field=models.CharField(default='', max_length=60),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(choices=[('unpaid', 'Unpaid')], default='unpaid', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='postal_code',
            field=models.CharField(default='', max_length=10),
        ),
        migrations.AddField(
            model_name='order',
            name='province',
            field=models.CharField(default='', max_length=60),
        ),
        migrations.AddField(
            model_name='order',
            name='recipient_name',
            field=models.CharField(default='', max_length=120),
        ),
    ]
