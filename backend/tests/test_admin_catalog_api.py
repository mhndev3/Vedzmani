"""Custom staff catalog API: permission gates and invariants are exercised at the HTTP boundary."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission

from apps.accounts.models import User

from apps.catalog.models import (
    Category,
    ColorVariant,
    Product,
    ProductSizeMeasurement,
    Size,
    VariantSize,
    VariantSizeMeasurement,
)
from apps.inventory.models import InventoryAdjustment
from tests.conftest import client_for, new_phone

pytestmark = pytest.mark.django_db


def test_customer_and_staff_without_model_permission_cannot_read_catalog_admin_api(customer_client, make_staff):
    assert customer_client.get("/api/admin/catalog/products/").status_code in (401, 403)
    staff_client = client_for(make_staff())
    assert staff_client.get("/api/admin/catalog/products/").status_code == 403


def test_view_permission_does_not_grant_product_write(make_staff, make_variant_size):
    product = make_variant_size().variant.product
    client = client_for(make_staff("catalog.view_product"))
    assert client.get("/api/admin/catalog/products/").status_code == 200
    assert client.get(f"/api/admin/catalog/products/{product.pk}/").status_code == 200
    assert client.post(
        "/api/admin/catalog/products/",
        {"name": "No write", "slug": "no-write", "category": product.category_id, "price": "1000"},
        content_type="application/json",
    ).status_code == 403
    assert client.patch(
        f"/api/admin/catalog/products/{product.pk}/",
        {"name": "No write"},
        content_type="application/json",
    ).status_code == 403


def test_product_create_update_and_read_only_color_summary(make_staff):
    category = Category.objects.create(name="لباس", slug="clothing")
    client = client_for(make_staff("catalog.add_product", "catalog.view_product", "catalog.change_product"))
    created = client.post(
        "/api/admin/catalog/products/",
        {
            "name": "بافت پایه",
            "slug": "basic-knit",
            "category": category.pk,
            "description": "توضیحات",
            "price": "1250000",
            "sale_price": "1100000",
            "is_active": False,
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    product_id = created.json()["id"]
    assert created.json()["price"] == "1250000"
    assert created.json()["colors"] == []

    changed = client.patch(
        f"/api/admin/catalog/products/{product_id}/",
        {"name": "بافت پایه جدید"},
        content_type="application/json",
    )
    assert changed.status_code == 200
    assert Product.objects.get(pk=product_id).name == "بافت پایه جدید"


def test_color_variant_and_size_are_created_without_direct_stock_write(make_staff):
    category = Category.objects.create(name="لباس", slug="clothing")
    size = Size.objects.create(code="m", label="متوسط")
    product = Product.objects.create(
        category=category, name="بافت", slug="knit", price=Decimal("1000000")
    )
    client = client_for(make_staff(
        "catalog.add_colorvariant", "catalog.view_colorvariant",
        "catalog.add_variantsize", "catalog.view_variantsize",
    ))
    color = client.post(
        "/api/admin/catalog/colors/",
        {"product": product.pk, "name": "آبی روشن", "slug": "sky-blue", "hex_color": "#87CEEB"},
        content_type="application/json",
    )
    assert color.status_code == 201, color.content
    color_data = color.json()
    assert color_data["product_code"].isdigit()

    size_response = client.post(
        "/api/admin/catalog/variant-sizes/",
        {"variant": color_data["id"], "size": size.pk, "sku": "KNIT-SKY-M", "stock_quantity": 99},
        content_type="application/json",
    )
    assert size_response.status_code == 201, size_response.content
    row = VariantSize.objects.get(sku="KNIT-SKY-M")
    assert row.stock_quantity == 0
    assert size_response.json()["stock_quantity"] == 0


def test_inventory_api_requires_add_permission_and_records_audited_adjustment(make_staff, make_variant_size):
    row = make_variant_size(stock=3)
    payload = {"variant_size": row.pk, "quantity_change": 2, "reason": "ورود کالای جدید"}

    no_permission = client_for(make_staff("catalog.view_variantsize"))
    assert no_permission.post(
        "/api/admin/inventory/adjustments/", payload, content_type="application/json"
    ).status_code == 403

    actor = make_staff("inventory.add_inventoryadjustment", "inventory.view_inventoryadjustment", "catalog.view_variantsize")
    client = client_for(actor)
    response = client.post(
        "/api/admin/inventory/adjustments/", payload, content_type="application/json"
    )
    assert response.status_code == 201, response.content
    row.refresh_from_db()
    assert row.stock_quantity == 5
    adjustment = InventoryAdjustment.objects.get()
    assert adjustment.created_by == actor
    assert adjustment.stock_after == 5
    assert adjustment.reason == "ورود کالای جدید"


def test_inventory_api_rejects_negative_result_without_changing_stock(make_staff, make_variant_size):
    row = make_variant_size(stock=1)
    client = client_for(make_staff("inventory.add_inventoryadjustment", "catalog.view_variantsize"))
    response = client.post(
        "/api/admin/inventory/adjustments/",
        {"variant_size": row.pk, "quantity_change": -2, "reason": "اصلاح"},
        content_type="application/json",
    )
    assert response.status_code == 409
    row.refresh_from_db()
    assert row.stock_quantity == 1
    assert not InventoryAdjustment.objects.exists()


def test_measurement_endpoints_support_shared_and_color_size_specific_values(make_staff, make_variant_size):
    row = make_variant_size()
    client = client_for(make_staff(
        "catalog.add_productsizemeasurement",
        "catalog.add_variantsizemeasurement",
    ))
    shared = client.post(
        "/api/admin/catalog/product-measurements/",
        {
            "product": row.variant.product_id,
            "size": row.size_id,
            "name": "عرض سینه",
            "value": "56",
            "unit": "سانتی‌متر",
            "position": 0,
        },
        content_type="application/json",
    )
    assert shared.status_code == 201, shared.content
    specific = client.post(
        "/api/admin/catalog/variant-size-measurements/",
        {
            "variant_size": row.pk,
            "name": "قد لباس",
            "value": "65",
            "unit": "سانتی‌متر",
            "position": 0,
        },
        content_type="application/json",
    )
    assert specific.status_code == 201, specific.content
    assert ProductSizeMeasurement.objects.count() == 1
    assert VariantSizeMeasurement.objects.count() == 1


def test_admin_api_does_not_offer_hard_delete(make_staff, make_variant_size):
    product = make_variant_size().variant.product
    client = client_for(make_staff("catalog.delete_product"))
    response = client.delete(f"/api/admin/catalog/products/{product.pk}/")
    assert response.status_code == 405
    assert Product.objects.filter(pk=product.pk).exists()


def test_non_staff_user_with_model_permission_is_still_denied():
    user = User.objects.create_user(new_phone())
    permission = Permission.objects.get(content_type__app_label="catalog", codename="view_product")
    user.user_permissions.add(permission)
    client = client_for(user)
    assert client.get("/api/admin/catalog/products/").status_code == 403
