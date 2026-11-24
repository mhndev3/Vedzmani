from django.db import migrations, models


def assign_existing_sizes_to_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Size = apps.get_model("catalog", "Size")
    through = Category.sizes.through
    database = schema_editor.connection.alias
    category_ids = list(Category.objects.using(database).values_list("id", flat=True))
    size_ids = list(Size.objects.using(database).values_list("id", flat=True))
    if category_ids and size_ids:
        through.objects.using(database).bulk_create(
            [
                through(category_id=category_id, size_id=size_id)
                for category_id in category_ids
                for size_id in size_ids
            ],
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0021_homepage_banner_groups")]

    operations = [
        migrations.AddField(
            model_name="category",
            name="sizes",
            field=models.ManyToManyField(blank=True, related_name="categories", to="catalog.size"),
        ),
        migrations.RunPython(assign_existing_sizes_to_categories, migrations.RunPython.noop),
    ]
