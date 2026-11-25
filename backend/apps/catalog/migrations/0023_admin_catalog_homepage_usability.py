from django.db import migrations, models


def mark_existing_homepage_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    database = schema_editor.connection.alias
    existing_positions = {
        "sweatshirts": 0,
        "knitwear": 1,
        "jeans": 2,
        "hoodies": 3,
        "leather-jackets": 4,
    }
    for slug, position in existing_positions.items():
        Category.objects.using(database).filter(slug=slug).update(
            is_homepage_featured=True,
            homepage_position=position,
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0022_category_allowed_sizes")]

    operations = [
        migrations.AddField(
            model_name="category",
            name="is_homepage_featured",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="category",
            name="homepage_position",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="homepagesection",
            name="section_label",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.RunPython(mark_existing_homepage_categories, migrations.RunPython.noop),
    ]
