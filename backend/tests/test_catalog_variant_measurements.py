"""Exact color + size measurements: a color-specific table must never leak into another color."""

import pytest
from django.test import Client

from apps.catalog.models import (
    Category, ColorVariant, Product, ProductSizeMeasurement, Size, VariantSize, VariantSizeMeasurement,
)

pytestmark = pytest.mark.django_db


def _product():
    category = Category.objects.create(name="Jeans", slug="jeans-x")
    size = Size.objects.create(code="31x", label="31", position=1)
    product = Product.objects.create(category=category, name="J", slug="j-x", price=100, is_active=True)
    rows = {}
    for slug in ("navy", "charcoal"):
        variant = ColorVariant.objects.create(product=product, name=slug, slug=slug)
        rows[slug] = VariantSize.objects.create(variant=variant, size=size, sku=f"sku-{slug}", stock_quantity=1)
    return product, size, rows


def test_color_specific_measurements_are_returned_per_exact_color_and_size():
    product, size, rows = _product()
    VariantSizeMeasurement.objects.create(variant_size=rows["navy"], name="waist", value="40", position=0)
    VariantSizeMeasurement.objects.create(variant_size=rows["charcoal"], name="waist", value="44", position=0)
    body = Client().get(f"/api/catalog/products/{product.slug}/").json()
    by_color = {c["slug"]: c["sizes"][0]["measurements"] for c in body["colors"]}
    assert by_color["navy"] == [{"name": "waist", "value": "40", "unit": ""}]
    assert by_color["charcoal"] == [{"name": "waist", "value": "44", "unit": ""}]


def test_product_level_measurements_remain_the_fallback_for_every_color():
    product, size, rows = _product()
    ProductSizeMeasurement.objects.create(product=product, size=size, name="waist", value="50", position=0)
    VariantSizeMeasurement.objects.create(variant_size=rows["navy"], name="waist", value="40", position=0)
    body = Client().get(f"/api/catalog/products/{product.slug}/").json()
    by_color = {c["slug"]: c["sizes"][0]["measurements"] for c in body["colors"]}
    assert by_color["navy"][0]["value"] == "40"
    assert by_color["charcoal"][0]["value"] == "50"
