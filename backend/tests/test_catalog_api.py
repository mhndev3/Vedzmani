from decimal import Decimal

import pytest
from django.test import Client

from apps.catalog.models import Category, ColorVariant, Product, Size, VariantImage, VariantSize

pytestmark = pytest.mark.django_db


def build(slug="basic-hoodie", active=True, variants=2):
    cat = Category.objects.get_or_create(slug="hoodie", defaults={"name": "Hoodie"})[0]
    p = Product.objects.create(category=cat, name="Basic Hoodie", slug=slug, price=Decimal("1000"), is_active=active)
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
    build()
    r = Client().get("/api/catalog/products/basic-hoodie/")
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == {"name": "Hoodie", "slug": "hoodie"}
    assert [c["slug"] for c in body["colors"]] == ["c0", "c1"]
    first = body["colors"][0]
    assert [s["size"] for s in first["sizes"]] == ["s", "m", "l"]
    assert [i["position"] for i in first["images"]] == [0, 1] and first["images"][0]["is_primary"]
    assert first["sizes"][0]["in_stock"] is False and body["colors"][1]["sizes"][0]["in_stock"] is True
    assert "stock_quantity" not in first["sizes"][0] and "storage_key" not in first["images"][0]


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
    with django_assert_max_num_queries(6):  # product, variants, images, sizes (+ prefetch of size)
        assert Client().get("/api/catalog/products/basic-hoodie/").status_code == 200


def test_write_methods_not_allowed():
    build()
    assert Client().post("/api/catalog/products/basic-hoodie/").status_code == 405
