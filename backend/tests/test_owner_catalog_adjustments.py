from decimal import Decimal
from io import StringIO

import pytest
from django.core.management.base import CommandError
from django.core.management import call_command

from apps.catalog.models import Category, ColorVariant, Product, Size, VariantImage, VariantSize
from apps.inventory.models import InventoryAdjustment

pytestmark = pytest.mark.django_db


IMAGE_PAIRS = (
    ("products/dors-two-tone-green-white/green-white/01.054b05e7af52.w1600.webp", "products/dors-two-tone-green-white/green-white/04.6cf2b0656227.w1600.webp"),
    ("products/dors-two-tone-grey-black/grey-black/01.ee1530f7ac6f.w1600.webp", "products/dors-two-tone-grey-black/grey-black/04.b3fbbcebf49c.w1600.webp"),
    ("products/dors-two-tone-black-red/black-red/01.37970861bb56.w1600.webp", "products/dors-two-tone-black-red/black-red/04.9f9053bd0416.w1600.webp"),
)


def seed_adjustment_catalog():
    category = Category.objects.create(name="آزمایش", slug="owner-adjustments-test")
    for index, pair in enumerate(IMAGE_PAIRS, start=2):
        product = Product.objects.create(category=category, product_code=f"0{index}", name=f"دورس {index}", slug=f"owner-dors-{index}", price=Decimal("100000"), is_active=True)
        variant = ColorVariant.objects.create(product=product, name=f"رنگ {index}", slug=f"color-{index}")
        for position, key in enumerate(pair):
            VariantImage.objects.create(variant=variant, storage_key=key.replace(".w1600.webp", ".webp"), display_storage_key=key, position=position * 3, is_primary=(position == 0), width=800, height=1000)

    west = Product.objects.create(category=category, product_code="01", name="وست جین", slug="owner-west-jeans", price=Decimal("200000"), is_active=True)
    blue = ColorVariant.objects.create(product=west, name="آبی روشن", slug="light-blue")
    xxl = Size.objects.create(code="xxl", label="XXL")
    variant_size = VariantSize.objects.create(variant=blue, size=xxl, sku="owner-west-jeans-blue-xxl", stock_quantity=0)
    return variant_size


def test_owner_adjustment_command_defaults_to_dry_run():
    variant_size = seed_adjustment_catalog()
    before = list(VariantImage.objects.order_by("storage_key").values_list("storage_key", "position", "is_primary"))
    output = StringIO()
    call_command("apply_owner_catalog_adjustments", stdout=output)
    assert "DRY_RUN_ONLY" in output.getvalue()
    assert variant_size.stock_quantity == 0
    assert list(VariantImage.objects.order_by("storage_key").values_list("storage_key", "position", "is_primary")) == before
    assert InventoryAdjustment.objects.count() == 0


def test_owner_adjustment_command_swaps_images_and_adds_one_stock_unit_atomically():
    variant_size = seed_adjustment_catalog()
    before = {}
    for pair in IMAGE_PAIRS:
        left = VariantImage.objects.get(display_storage_key=pair[0])
        right = VariantImage.objects.get(display_storage_key=pair[1])
        before[pair] = (left.position, left.is_primary, right.position, right.is_primary)

    call_command("apply_owner_catalog_adjustments", apply=True, stdout=StringIO())

    for pair in IMAGE_PAIRS:
        left = VariantImage.objects.get(display_storage_key=pair[0])
        right = VariantImage.objects.get(display_storage_key=pair[1])
        left_pos, left_primary, right_pos, right_primary = before[pair]
        assert (left.position, left.is_primary, right.position, right.is_primary) == (right_pos, right_primary, left_pos, left_primary)
    variant_size.refresh_from_db()
    assert variant_size.stock_quantity == 1
    assert InventoryAdjustment.objects.get(variant_size=variant_size).quantity_change == 1
    with pytest.raises(CommandError, match="already applied"):
        call_command("apply_owner_catalog_adjustments", apply=True, stdout=StringIO())
    variant_size.refresh_from_db()
    assert variant_size.stock_quantity == 1


def test_joggers_category_name_is_updated_by_catalog_migration():
    category = Category.objects.get(slug="joggers")
    assert category.name == "شلوار جاگر"
