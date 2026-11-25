import pytest

from apps.catalog.models import Category, Collection, ColorVariant, Product, Size, VariantSize
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def create_permissions():
    return (
        "catalog.add_product",
        "catalog.add_colorvariant",
        "catalog.add_variantsize",
    )


def test_staff_can_create_product_with_multiple_colors_and_sizes_atomically(make_staff):
    category = Category.objects.create(name="بافت", slug="bulk-create-knitwear-atomic")
    collection = Collection.objects.create(name="پاییز", slug="bulk-create-autumn-collection")
    small = Size.objects.create(code="bulk-s", label="Small", position=1)
    medium = Size.objects.create(code="bulk-m", label="Medium", position=2)
    client = client_for(make_staff(*create_permissions()))

    response = client.post(
        "/api/admin/catalog/products/create-with-variants/",
        {
            "name": "بافت چندرنگ",
            "slug": "admin-bulk-multi-color-knit",
            "description": "توضیحات محصول",
            "price": "850000",
            "sale_price": "790000",
            "category": category.pk,
            "collections": [collection.pk],
            "colors": [
                {
                    "name": "آبی",
                    "slug": "blue",
                    "hex_color": "#87CEEB",
                    "sizes": [
                        {"size": small.pk, "sku": "KNIT-BLUE-S"},
                        {"size": medium.pk, "sku": "KNIT-BLUE-M"},
                    ],
                },
                {
                    "name": "مشکی",
                    "slug": "black",
                    "hex_color": "#000000",
                    "sizes": [
                        {"size": small.pk, "sku": "KNIT-BLACK-S"},
                        {"size": medium.pk, "sku": "KNIT-BLACK-M"},
                    ],
                },
            ],
        },
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    product = Product.objects.get(slug="admin-bulk-multi-color-knit")
    assert product.is_active is False
    assert list(product.collections.values_list("pk", flat=True)) == [collection.pk]

    colors = list(ColorVariant.objects.filter(product=product).order_by("position"))
    assert [color.name for color in colors] == ["آبی", "مشکی"]
    assert all(color.product_code and color.product_code.isdecimal() for color in colors)
    assert VariantSize.objects.filter(variant__product=product).count() == 4
    assert set(
        VariantSize.objects.filter(variant__product=product).values_list("sku", flat=True)
    ) == {"KNIT-BLUE-S", "KNIT-BLUE-M", "KNIT-BLACK-S", "KNIT-BLACK-M"}
    assert set(
        VariantSize.objects.filter(variant__product=product).values_list("stock_quantity", flat=True)
    ) == {0}
    assert len(response.json()["colors"]) == 2
    assert sum(len(color["sizes"]) for color in response.json()["colors"]) == 4


def test_bulk_product_creation_generates_internal_skus_when_staff_does_not_provide_them(make_staff):
    category = Category.objects.create(name="اکسسوری", slug="bulk-create-auto-sku-accessories")
    size = Size.objects.create(code="auto-sku-one", label="تک سایز")
    client = client_for(make_staff(*create_permissions()))
    response = client.post(
        "/api/admin/catalog/products/create-with-variants/",
        {
            "name": "کیف روزمره", "slug": "admin-bulk-auto-sku-bag", "price": "450000",
            "category": category.pk,
            "colors": [
                {"name": "قهوه‌ای", "slug": "brown", "sizes": [{"size": size.pk}]},
                {"name": "مشکی", "slug": "black", "sizes": [{"size": size.pk}]},
            ],
        },
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    rows = list(VariantSize.objects.filter(variant__product__slug="admin-bulk-auto-sku-bag").order_by("id"))
    assert len(rows) == 2
    assert len({row.sku for row in rows}) == 2
    assert all(row.sku.startswith("VZ-") for row in rows)
    assert all(row.stock_quantity == 0 for row in rows)


def test_bulk_product_creation_requires_all_model_add_permissions(make_staff):
    category = Category.objects.create(name="لباس", slug="bulk-create-clothes-permission")
    size = Size.objects.create(code="bulk-invalid-m", label="Medium")
    client = client_for(make_staff("catalog.add_product", "catalog.add_colorvariant"))

    response = client.post(
        "/api/admin/catalog/products/create-with-variants/",
        {
            "name": "محصول",
            "slug": "admin-bulk-no-size-permission",
            "price": "100000",
            "category": category.pk,
            "colors": [
                {
                    "name": "آبی",
                    "slug": "blue",
                    "hex_color": "#0000ff",
                    "sizes": [{"size": size.pk, "sku": "PRODUCT-BLUE-M"}],
                }
            ],
        },
        content_type="application/json",
    )

    assert response.status_code == 403
    assert not Product.objects.filter(slug="admin-bulk-no-size-permission").exists()


def test_bulk_product_creation_rejects_duplicate_skus_without_partial_records(make_staff):
    category = Category.objects.create(name="لباس", slug="bulk-create-clothing-invalid")
    size = Size.objects.create(code="bulk-dup-m", label="Medium")
    client = client_for(make_staff(*create_permissions()))

    response = client.post(
        "/api/admin/catalog/products/create-with-variants/",
        {
            "name": "محصول نامعتبر",
            "slug": "admin-bulk-duplicate-sku",
            "price": "100000",
            "category": category.pk,
            "colors": [
                {
                    "name": "آبی",
                    "slug": "blue",
                    "hex_color": "#0000ff",
                    "sizes": [{"size": size.pk, "sku": "DUPLICATE-SKU"}],
                },
                {
                    "name": "مشکی",
                    "slug": "black",
                    "hex_color": "#000000",
                    "sizes": [{"size": size.pk, "sku": "DUPLICATE-SKU"}],
                },
            ],
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not Product.objects.filter(slug="admin-bulk-duplicate-sku").exists()
    assert not ColorVariant.objects.filter(product__slug="admin-bulk-duplicate-sku").exists()
    assert not VariantSize.objects.filter(variant__product__slug="admin-bulk-duplicate-sku").exists()


def test_bulk_product_creation_generates_product_and_color_slugs_for_staff(make_staff):
    category = Category.objects.create(name="لباس", slug="bulk-create-generated-slugs")
    size = Size.objects.create(code="generated-slug-one", label="تک سایز")
    client = client_for(make_staff(*create_permissions()))

    response = client.post(
        "/api/admin/catalog/products/create-with-variants/",
        {
            "name": "پیراهن ساده",
            "price": "390000",
            "category": category.pk,
            "colors": [
                {"name": "آبی", "sizes": [{"size": size.pk}]},
                {"name": "مشکی", "sizes": [{"size": size.pk}]},
            ],
        },
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    payload = response.json()
    assert payload["slug"].startswith("product-")
    assert len(payload["slug"]) <= 220
    assert [color["slug"].startswith("color-") for color in payload["colors"]] == [True, True]
    product = Product.objects.get(pk=payload["id"])
    assert product.slug == payload["slug"]
    assert len(set(product.color_variants.values_list("slug", flat=True))) == 2
