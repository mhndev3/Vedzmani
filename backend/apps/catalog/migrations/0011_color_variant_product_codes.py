from django.db import migrations, models


def populate_color_variant_codes(apps, schema_editor):
    ColorVariant = apps.get_model("catalog", "ColorVariant")
    db = schema_editor.connection.alias
    used = set()

    variants = ColorVariant.objects.using(db).select_related("product").order_by(
        "product_id", "position", "id"
    )
    for variant in variants.iterator():
        base = variant.product.product_code or f"VZ-{variant.product_id}"
        suffix = f"-{variant.slug.upper()}"
        if len(suffix) >= 40:
            suffix = f"-V{variant.pk}"
        candidate = f"{base[:40 - len(suffix)]}{suffix}"
        if candidate in used:
            suffix = f"-V{variant.pk}"
            candidate = f"{base[:40 - len(suffix)]}{suffix}"
        counter = 2
        while candidate in used:
            suffix = f"-V{variant.pk}-{counter}"
            candidate = f"{base[:40 - len(suffix)]}{suffix}"
            counter += 1
        variant.product_code = candidate
        variant.save(update_fields=["product_code"])
        used.add(candidate)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0010_rename_joggers_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="colorvariant",
            name="product_code",
            field=models.CharField(
                blank=True,
                max_length=40,
                null=True,
                unique=True,
                verbose_name="کد محصول / رنگ",
            ),
        ),
        migrations.RunPython(populate_color_variant_codes, migrations.RunPython.noop),
    ]
