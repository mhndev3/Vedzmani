from django.db import migrations


PRODUCT_SLUG = "vedzmani-test-product"
CATEGORY_SLUG = "test-products"
SIZE_CODE = "free"
VARIANT_SLUG = "white"
SKU = "TEST-FREE-001"


def create_temporary_test_product(apps, schema_editor):
    db = schema_editor.connection.alias
    Category = apps.get_model("catalog", "Category")
    Size = apps.get_model("catalog", "Size")
    Product = apps.get_model("catalog", "Product")
    ColorVariant = apps.get_model("catalog", "ColorVariant")
    VariantSize = apps.get_model("catalog", "VariantSize")
    InventoryAdjustment = apps.get_model("inventory", "InventoryAdjustment")

    category, _ = Category.objects.using(db).get_or_create(
        slug=CATEGORY_SLUG,
        defaults={
            "name": "محصولات آزمایشی",
            "position": 99,
            "is_active": True,
        },
    )
    size, _ = Size.objects.using(db).get_or_create(
        code=SIZE_CODE,
        defaults={"label": "فری سایز", "position": 99},
    )
    Category.sizes.through.objects.using(db).get_or_create(
        category_id=category.pk,
        size_id=size.pk,
    )

    product, _ = Product.objects.using(db).get_or_create(
        slug=PRODUCT_SLUG,
        defaults={
            "product_code": "TEST-001",
            "name": "تست",
            "category_id": category.pk,
            "description": "محصول آزمایشی موقت برای بررسی نمایش فروشگاه و سبد خرید.",
            "price": 1000,
            "is_active": True,
        },
    )
    variant, _ = ColorVariant.objects.using(db).get_or_create(
        product_id=product.pk,
        slug=VARIANT_SLUG,
        defaults={
            "name": "سفید",
            "hex_color": "#FFFFFF",
            "is_active": True,
            "position": 0,
        },
    )
    variant_size, created = VariantSize.objects.using(db).get_or_create(
        variant_id=variant.pk,
        size_id=size.pk,
        defaults={
            "sku": SKU,
            "stock_quantity": 1,
            "is_active": True,
        },
    )
    if created:
        InventoryAdjustment.objects.using(db).create(
            variant_size_id=variant_size.pk,
            quantity_change=1,
            stock_after=1,
            reason="Initial stock for temporary storefront test product",
            created_by=None,
        )


def remove_temporary_test_product(apps, schema_editor):
    db = schema_editor.connection.alias
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")
    InventoryAdjustment = apps.get_model("inventory", "InventoryAdjustment")

    product = Product.objects.using(db).filter(slug=PRODUCT_SLUG).first()
    if product:
        InventoryAdjustment.objects.using(db).filter(
            variant_size__variant__product_id=product.pk
        ).delete()
        product.delete()

    category = Category.objects.using(db).filter(slug=CATEGORY_SLUG).first()
    if category and not Product.objects.using(db).filter(category_id=category.pk).exists():
        category.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0023_admin_catalog_homepage_usability"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_temporary_test_product,
            remove_temporary_test_product,
        ),
    ]
