# Add configurable category fields and their per-product values.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0019_category_image")]

    operations = [
        migrations.AddField(
            model_name="category",
            name="product_fields",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="product",
            name="attributes",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
