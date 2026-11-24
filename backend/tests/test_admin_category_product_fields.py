import pytest
from rest_framework.test import APIClient

from apps.catalog.models import (
    Category,
    Product,
    ProductSizeDescription,
    ProductSizeMeasurement,
    Size,
    VariantSize,
)
from tests.conftest import client_for


pytestmark = pytest.mark.django_db


def field_schema():
    return [
        {"key": "fabric", "label": "جنس پارچه", "type": "text", "unit": "", "required": False},
        {"key": "length_cm", "label": "قد لباس", "type": "number", "unit": "سانتی‌متر", "required": True},
    ]


def create_product_payload(category, size, *, slug="category-fields-product", attributes=None):
    return {
        "name": "بافت دسته‌بندی‌دار",
        "slug": slug,
        "description": "//",
        "price": "950000",
        "sale_price": None,
        "category": category.pk,
        "attributes": attributes or {},
        "colors": [
            {
                "name": "آبی",
                "slug": "blue",
                "hex_color": "#87CEEB",
                "sizes": [{"size": size.pk, "sku": f"SKU-{slug}-BLUE-M"}],
            }
        ],
    }


def test_category_admin_accepts_valid_product_field_schema_and_rejects_duplicate_keys(make_staff):
    editor = client_for(make_staff("catalog.add_category", "catalog.view_category", "catalog.change_category"))
    created = editor.post(
        "/api/admin/catalog/categories/",
        {
            "name": "لباس",
            "slug": "category-product-fields",
            "product_fields": field_schema(),
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    category = Category.objects.get(pk=created.json()["id"])
    assert category.product_fields == field_schema()

    invalid_schema = [
        {"key": "same_key", "label": "فیلد اول", "type": "text", "unit": "", "required": False},
        {"key": "same_key", "label": "فیلد دوم", "type": "number", "unit": "", "required": False},
    ]
    invalid = editor.patch(
        f"/api/admin/catalog/categories/{category.pk}/",
        {"product_fields": invalid_schema},
        content_type="application/json",
    )
    assert invalid.status_code == 400
    category.refresh_from_db()
    assert category.product_fields == field_schema()


def test_create_product_validates_category_fields_and_hides_double_slash_values(make_staff):
    category = Category.objects.create(
        name="بافت",
        slug="category-product-fields-knitwear",
        product_fields=field_schema(),
    )
    size = Size.objects.create(code="cat-fields-m", label="متوسط")
    editor = client_for(make_staff(
        "catalog.add_product",
        "catalog.add_colorvariant",
        "catalog.add_variantsize",
        "catalog.view_product",
        "catalog.change_product",
    ))

    missing_required = editor.post(
        "/api/admin/catalog/products/create-with-variants/",
        create_product_payload(category, size, slug="category-fields-missing-required", attributes={"fabric": "پنبه"}),
        content_type="application/json",
    )
    assert missing_required.status_code == 400
    assert not Product.objects.filter(slug="category-fields-missing-required").exists()

    created = editor.post(
        "/api/admin/catalog/products/create-with-variants/",
        create_product_payload(
            category,
            size,
            attributes={"fabric": "//", "length_cm": "125"},
        ),
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    product = Product.objects.get(pk=created.json()["id"])
    assert product.attributes == {"fabric": "", "length_cm": "125"}
    assert product.description == ""

    changed = editor.patch(
        f"/api/admin/catalog/products/{product.pk}/",
        {"description": "//"},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    product.refresh_from_db()
    assert product.description == ""

    product.is_active = True
    product.save(update_fields=["is_active"])
    size_measurement = ProductSizeMeasurement.objects.create(
        product=product,
        size=size,
        name="دور سینه",
        value="//",
        unit="سانتی‌متر",
        position=0,
    )
    ProductSizeDescription.objects.create(product=product, size=size, description="//")
    assert size_measurement.pk

    public = APIClient().get(f"/api/catalog/products/{product.slug}/")
    assert public.status_code == 200, public.content
    assert public.data["description"] == ""
    assert public.data["category"]["product_fields"] == field_schema()
    assert public.data["attributes"] == {"length_cm": "125"}
    assert public.data["colors"][0]["sizes"][0]["measurements"] == []
    assert public.data["colors"][0]["sizes"][0]["size_description"] == ""


def test_product_attributes_must_match_selected_category_schema(make_staff):
    first = Category.objects.create(
        name="بافت",
        slug="category-fields-first",
        product_fields=field_schema(),
    )
    second = Category.objects.create(
        name="شلوار",
        slug="category-fields-second",
        product_fields=[
            {"key": "waist_cm", "label": "دور کمر", "type": "number", "unit": "سانتی‌متر", "required": True},
        ],
    )
    size = Size.objects.create(code="cat-fields-s", label="کوچک")
    editor = client_for(make_staff("catalog.add_product", "catalog.add_colorvariant", "catalog.add_variantsize"))

    response = editor.post(
        "/api/admin/catalog/products/create-with-variants/",
        create_product_payload(first, size, slug="category-fields-unknown", attributes={"waist_cm": "80"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert not Product.objects.filter(slug="category-fields-unknown").exists()
    assert second.product_fields[0]["key"] == "waist_cm"
