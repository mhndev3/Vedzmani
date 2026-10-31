from django.db import migrations, models

from apps.catalog.validators import validate_storage_key


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_leather_jackets_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="variantimage",
            name="thumbnail_storage_key",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                validators=[validate_storage_key],
            ),
        ),
        migrations.AddField(
            model_name="variantimage",
            name="display_storage_key",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                validators=[validate_storage_key],
            ),
        ),
        migrations.AddField(
            model_name="variantimage",
            name="optimization_version",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
