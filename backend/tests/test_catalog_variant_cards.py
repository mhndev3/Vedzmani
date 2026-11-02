from decimal import Decimal
from uuid import uuid4

import pytest
from django.test import Client

from apps.catalog.models import Category, ColorVariant, Product, Size, VariantImage, VariantSize

pytestmark = pytest.mark.django_db

URL = "/api/catalog/variant-products/"


def make_product():
    suffix = uuid4().hex[:10]
    category, _ = Category.objects.get_or_create(slug="knitwear", defaults={"name": "بافت"})
    product = Product.objects.create(
        category=category,
        product_code=f"VZ-KNIT-{suffix.upper()}",
        name="بافت یقه‌دار",
        slug=f"collared-knit-{suffix}",
        description="بافت گرم",
        price=Decimal("1250000"),
        is_active=True,
    )
    size, _ = Size.objects.get_or_create(code="m", defaults={"label": "M"})
    black = ColorVariant.objects.create(product=product, name="مشکی", slug="black", hex_color="#111111", position=0)
    white = ColorVariant.objects.create(product=product, name="سفید", slug="white", hex_color="#ffffff", position=1)
    VariantImage.objects.create(
        variant=black, storage_key=f"knit/{suffix}-black.webp", alt_text="بافت یقه‌دار مشکی",
        position=0, is_primary=True, width=600, height=800,
    )
    VariantImage.objects.create(
        variant=white, storage_key=f"knit/{suffix}-white.webp", alt_text="بافت یقه‌دار سفید",
        position=0, is_primary=True, width=600, height=800,
    )
    VariantSize.objects.create(variant=black, size=size, sku=f"KNIT-{suffix}-BLK-M", stock_quantity=4)
    VariantSize.objects.create(variant=white, size=size, sku=f"KNIT-{suffix}-WHT-M", stock_quantity=0)
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
    assert black["code"] and white["code"]
    assert black["code"] != white["code"]
    assert black["code"].startswith(product.product_code)
    assert white["code"].startswith(product.product_code)
    assert black["slug"] == white["slug"] == product.slug
    assert black["category"] == white["category"] == {"name": "بافت", "slug": "knitwear"}
    assert black["color"] == {"name": "مشکی", "slug": "black", "hex_color": "#111111"}
    assert white["color"] == {"name": "سفید", "slug": "white", "hex_color": "#ffffff"}
    assert black["image"]["url"] == f"/media/knit/{product.slug.removeprefix('collared-knit-')}-black.webp"
    assert white["image"]["url"] == f"/media/knit/{product.slug.removeprefix('collared-knit-')}-white.webp"
    assert black["in_stock"] is True
    assert white["in_stock"] is False

    detail = Client().get(f"/api/catalog/products/{product.slug}/").json()
    detail_codes = {color["slug"]: color["product_code"] for color in detail["colors"]}
    assert detail_codes == {"black": black["code"], "white": white["code"]}

    code_search = Client().get(URL, {"search": white["code"]}).json()
    assert code_search["count"] == 1
    assert code_search["results"][0]["code"] == white["code"]

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
    response = Client().get(URL).json()
    assert response["count"] == 1
    assert response["results"][0]["color"]["slug"] == "black"
    Product.objects.filter(pk=product.pk).update(is_active=False)
    assert Client().get(URL).json()["count"] == 0
