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
            "slug": "multi-color-knit",
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


def test_bulk_product_creation_requires_all_model_add_permissions(make_staff):
    category = Category.objects.create(name="لباس", slug="bulk-create-clothes-permission")
    size = Size.objects.create(code="bulk-invalid-m", label="Medium")
    client = client_for(make_staff("catalog.add_product", "catalog.add_colorvariant"))

    response = client.post(
        "/api/admin/catalog/products/create-with-variants/",
        {
            "name": "محصول",
            "slug": "product-without-size-permission",
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
    size = Size.objects.create(code="m", label="Medium")
    client = client_for(make_staff(*create_permissions()))

    response = client.post(
        "/api/admin/catalog/products/create-with-variants/",
        {
            "name": "محصول نامعتبر",
            "slug": "duplicate-sku-product",
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
