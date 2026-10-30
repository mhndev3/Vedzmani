from django.db import migrations


def seed_knitwear_category(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    db = schema_editor.connection.alias
    Category.objects.using(db).update_or_create(
        slug="knitwear",
        defaults={"name": "بافت", "position": 11, "is_active": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_product_size_measurements"),
    ]

    operations = [
        migrations.RunPython(seed_knitwear_category, migrations.RunPython.noop),
    ]
