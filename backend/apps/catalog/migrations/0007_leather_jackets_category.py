from django.db import migrations


def add_leather_jackets_category(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")
    category, _ = Category.objects.get_or_create(
        slug="leather-jackets",
        defaults={"name": "جکت چرم", "position": 13, "is_active": True},
    )
    # Product 09 is the leather bomber jacket in the owner's 13-product catalog.
    Product.objects.filter(product_code="09").update(category=category)


def reverse_leather_jackets_category(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")
    old_category = Category.objects.filter(slug="jackets").first()
    new_category = Category.objects.filter(slug="leather-jackets").first()
    if old_category and new_category:
        Product.objects.filter(product_code="09", category=new_category).update(category=old_category)
    if new_category and not Product.objects.filter(category=new_category).exists():
        new_category.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_variant_size_measurements"),
    ]

    operations = [
        migrations.RunPython(add_leather_jackets_category, reverse_leather_jackets_category),
    ]
