from decimal import Decimal

import pytest
from django.test import Client

from apps.catalog.models import (
    Category, ColorVariant, Product, ProductSizeDescription, ProductSizeMeasurement, Size,
    VariantImage, VariantSize, VariantSizeDescription,
)

pytestmark = pytest.mark.django_db


def build(slug="basic-hoodie", active=True, variants=2):
    cat = Category.objects.get_or_create(slug="hoodie", defaults={"name": "Hoodie"})[0]
    p = Product.objects.create(category=cat, product_code=f"VZ-{slug.upper()}", name="Basic Hoodie", slug=slug, price=Decimal("1000"), is_active=active)
    sizes = [Size.objects.get_or_create(code=c, defaults={"label": c.upper(), "position": i})[0] for i, c in enumerate("sml")]
    for n in range(variants):
        v = ColorVariant.objects.create(product=p, name=f"C{n}", slug=f"c{n}", position=n)
        for s in sizes:
            VariantSize.objects.create(variant=v, size=s, sku=f"{slug}-{n}-{s.code}", stock_quantity=n)
        for pos in range(2):
            VariantImage.objects.create(
                variant=v, storage_key=f"{slug}/{n}/{pos}.webp", position=pos, is_primary=pos == 0, width=10, height=10
            )
    return p


def test_detail_returns_nested_structure():
    product = build()
    size_m = Size.objects.get(code="m")
    size_l = Size.objects.get(code="l")
    ProductSizeMeasurement.objects.create(
        product=product, size=size_m, name="عرض سینه", value="56", unit="سانتی‌متر", position=0
    )
    ProductSizeMeasurement.objects.create(
        product=product, size=size_m, name="قد کار", value="64", unit="سانتی‌متر", position=1
    )
    ProductSizeMeasurement.objects.create(
        product=product, size=size_l, name="عرض سینه", value="59", unit="سانتی‌متر", position=0
    )
    r = Client().get("/api/catalog/products/basic-hoodie/")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "VZ-BASIC-HOODIE"
    assert body["category"] == {"name": "Hoodie", "slug": "hoodie"}
    assert [c["slug"] for c in body["colors"]] == ["c0", "c1"]
    first = body["colors"][0]
    assert [s["size"] for s in first["sizes"]] == ["s", "m", "l"]
    assert [i["position"] for i in first["images"]] == [0, 1] and first["images"][0]["is_primary"]
    assert first["sizes"][0]["in_stock"] is False and first["sizes"][0]["stock_quantity"] == 0
    assert first["sizes"][1]["measurements"] == [
        {"name": "عرض سینه", "value": "56", "unit": "سانتی‌متر"},
        {"name": "قد کار", "value": "64", "unit": "سانتی‌متر"},
    ]
    assert first["sizes"][2]["measurements"] == [
        {"name": "عرض سینه", "value": "59", "unit": "سانتی‌متر"},
    ]
    assert body["colors"][1]["sizes"][1]["measurements"] == first["sizes"][1]["measurements"]
    assert body["colors"][1]["sizes"][0]["measurements"] == []
    assert body["colors"][1]["sizes"][0]["in_stock"] is True
    assert body["colors"][1]["sizes"][0]["stock_quantity"] == 1
    assert "storage_key" not in first["images"][0]



def test_size_description_falls_back_and_color_size_override_wins():
    product = build(slug="described-hoodie")
    size_m = Size.objects.get(code="m")
    size_l = Size.objects.get(code="l")
    ProductSizeDescription.objects.create(
        product=product, size=size_m, description="توضیح مشترک سایز M"
    )
    black = ColorVariant.objects.get(product=product, slug="c0")
    white = ColorVariant.objects.get(product=product, slug="c1")
    VariantSizeDescription.objects.create(
        variant_size=white.sizes.get(size=size_m),
        description="توضیح اختصاصی رنگ سفید و سایز M",
    )

    body = Client().get("/api/catalog/products/described-hoodie/").json()
    black_sizes = {row["size"]: row for row in body["colors"][0]["sizes"]}
    white_sizes = {row["size"]: row for row in body["colors"][1]["sizes"]}

    assert black_sizes["m"]["size_description"] == "توضیح مشترک سایز M"
    assert white_sizes["m"]["size_description"] == "توضیح اختصاصی رنگ سفید و سایز M"
    assert black_sizes["l"]["size_description"] == ""
    assert white_sizes["l"]["size_description"] == ""



def test_inactive_product_and_inactive_children_hidden():
    build(slug="hidden", active=False)
    assert Client().get("/api/catalog/products/hidden/").status_code == 404
    build()
    ColorVariant.objects.filter(slug="c1").update(is_active=False)
    VariantImage.objects.filter(position=1).update(is_active=False)
    body = Client().get("/api/catalog/products/basic-hoodie/").json()
    assert [c["slug"] for c in body["colors"]] == ["c0"]
    assert len(body["colors"][0]["images"]) == 1


def test_inactive_category_hides_product():
    build()
    Category.objects.update(is_active=False)
    assert Client().get("/api/catalog/products/basic-hoodie/").status_code == 404


def test_detail_query_count_is_constant(django_assert_max_num_queries):
    build(variants=5)
    with django_assert_max_num_queries(9):  # fixed prefetches, including both description scopes
        assert Client().get("/api/catalog/products/basic-hoodie/").status_code == 200


def test_write_methods_not_allowed():
    build()
    assert Client().post("/api/catalog/products/basic-hoodie/").status_code == 405



def test_detail_orders_primary_image_before_lower_position_images():
    product = build(slug="primary-image-order")
    variant = ColorVariant.objects.get(product=product, slug="c0")
    VariantImage.objects.filter(variant=variant, position=0).update(is_primary=False)
    VariantImage.objects.filter(variant=variant, position=1).update(
        is_primary=True,
        thumbnail_storage_key="primary-image-order/0/1.w640.webp",
        display_storage_key="primary-image-order/0/1.w1600.webp",
    )

    response = Client().get("/api/catalog/products/primary-image-order/")
    assert response.status_code == 200
    images = response.json()["colors"][0]["images"]
    assert [image["position"] for image in images] == [1, 0]
    assert images[0]["is_primary"] is True
    assert images[0]["url"] == "/media/primary-image-order/0/1.webp"
    assert images[0]["thumbnail_url"] == "/media/primary-image-order/0/1.w640.webp"
    assert images[0]["display_url"] == "/media/primary-image-order/0/1.w1600.webp"


def test_product_listing_uses_thumbnail_image_when_a_rendition_exists():
    product = build(slug="listing-thumbnail")
    variant = ColorVariant.objects.get(product=product, slug="c0")
    VariantImage.objects.filter(variant=variant, position=0).update(
        thumbnail_storage_key="listing-thumbnail/0/0.w640.webp"
    )

    response = Client().get("/api/catalog/products/")
    assert response.status_code == 200
    item = next(row for row in response.json()["results"] if row["slug"] == "listing-thumbnail")
    assert item["image"]["url"] == "/media/listing-thumbnail/0/0.webp"
    assert item["image"]["thumbnail_url"] == "/media/listing-thumbnail/0/0.w640.webp"
