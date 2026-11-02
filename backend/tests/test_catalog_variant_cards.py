from decimal import Decimal

import pytest
from django.test import Client

from apps.catalog.models import Category, ColorVariant, Product, Size, VariantImage, VariantSize

pytestmark = pytest.mark.django_db

URL = "/api/catalog/variant-products/"


def make_product():
    category = Category.objects.create(name="بافت", slug="knitwear")
    product = Product.objects.create(
        category=category,
        product_code="VZ-KNIT-01",
        name="بافت یقه‌دار",
        slug="collared-knit",
        description="بافت گرم",
        price=Decimal("1250000"),
        is_active=True,
    )
    size = Size.objects.create(code="m", label="M")
    black = ColorVariant.objects.create(product=product, name="مشکی", slug="black", hex_color="#111111", position=0)
    white = ColorVariant.objects.create(product=product, name="سفید", slug="white", hex_color="#ffffff", position=1)
    VariantImage.objects.create(
        variant=black, storage_key="knit/black.webp", alt_text="بافت یقه‌دار مشکی",
        position=0, is_primary=True, width=600, height=800,
    )
    VariantImage.objects.create(
        variant=white, storage_key="knit/white.webp", alt_text="بافت یقه‌دار سفید",
        position=0, is_primary=True, width=600, height=800,
    )
    VariantSize.objects.create(variant=black, size=size, sku="KNIT-BLK-M", stock_quantity=4)
    VariantSize.objects.create(variant=white, size=size, sku="KNIT-WHT-M", stock_quantity=0)
    return product


def test_catalog_returns_one_independent_card_per_active_color_with_its_own_image_and_stock():
    product = make_product()
    response = Client().get(URL)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    black, white = body["results"]
    assert black["id"] == white["id"] == product.id
    assert black["variant_id"] != white["variant_id"]
    assert black["slug"] == white["slug"] == product.slug
    assert black["category"] == white["category"] == {"name": "بافت", "slug": "knitwear"}
    assert black["color"] == {"name": "مشکی", "slug": "black", "hex_color": "#111111"}
    assert white["color"] == {"name": "سفید", "slug": "white", "hex_color": "#ffffff"}
    assert black["image"]["url"] == "/media/knit/black.webp"
    assert white["image"]["url"] == "/media/knit/white.webp"
    assert black["in_stock"] is True
    assert white["in_stock"] is False
    for item in body["results"]:
        assert set(item) == {
            "id", "variant_id", "name", "slug", "code", "price", "sale_price",
            "category", "color", "in_stock", "image",
        }
        assert "sku" not in item and "stock_quantity" not in item


def test_color_and_size_filters_apply_to_the_same_variant_row():
    make_product()
    response = Client().get(URL, {"color": "white", "size": "m", "in_stock": "true"})
    assert response.status_code == 200
    assert response.json()["count"] == 0
    response = Client().get(URL, {"color": "black", "size": "m", "in_stock": "true"})
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["color"]["slug"] == "black"


def test_search_matches_variant_color_name_and_category_is_preserved():
    make_product()
    response = Client().get(URL, {"search": "مشکی", "category": "knitwear"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["color"]["slug"] == "black"


def test_inactive_variants_and_products_are_not_listed():
    product = make_product()
    ColorVariant.objects.filter(product=product, slug="white").update(is_active=False)
    Product.objects.filter(pk=product.pk).update(is_active=False)
    assert Client().get(URL).json()["count"] == 0
