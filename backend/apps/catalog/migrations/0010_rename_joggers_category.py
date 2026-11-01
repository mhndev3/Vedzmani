from django.db import migrations


def rename_joggers_category(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    db = schema_editor.connection.alias
    Category.objects.using(db).filter(slug="joggers").update(name="شلوار جاگر")


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_favorite"),
    ]

    operations = [
        migrations.RunPython(rename_joggers_category, migrations.RunPython.noop),
    ]
