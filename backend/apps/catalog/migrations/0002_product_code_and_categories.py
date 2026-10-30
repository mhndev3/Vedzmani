from django.db import migrations, models


CATEGORIES = [
    ("sweatshirts", "دورس"),
    ("shirts", "پیراهن"),
    ("t-shirts", "تی شرت"),
    ("hoodies", "هودی"),
    ("coats", "کاپشن"),
    ("jackets", "جکت"),
    ("jeans", "شلوار جین"),
    ("trousers", "شلوار پارچه ای"),
    ("joggers", "جاگر"),
    ("sneakers", "کتونی"),
    ("accessories", "اکسسوری"),
]


def backfill_product_codes(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    db = schema_editor.connection.alias
    for product in Product.objects.using(db).filter(product_code__isnull=True).iterator():
        Product.objects.using(db).filter(pk=product.pk).update(product_code=f"VZ-{product.pk:06d}")


def seed_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    db = schema_editor.connection.alias
    for position, (slug, name) in enumerate(CATEGORIES):
        Category.objects.using(db).update_or_create(
            slug=slug,
            defaults={"name": name, "position": position, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="product_code",
            field=models.CharField(blank=True, max_length=40, null=True, unique=True),
        ),
        migrations.RunPython(backfill_product_codes, migrations.RunPython.noop),
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
