# Add an optional uploaded image to storefront categories.
import apps.catalog.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0018_banner_theme_revisions")]

    operations = [
        migrations.AddField(
            model_name="category",
            name="image",
            field=models.ImageField(blank=True, default="", upload_to=apps.catalog.models.category_image_upload_to),
        ),
    ]
