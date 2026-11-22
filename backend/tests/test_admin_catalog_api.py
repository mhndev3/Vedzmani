"""Custom staff catalog API: permission gates and invariants are exercised at the HTTP boundary."""
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission

from apps.accounts.models import User

from apps.catalog.models import (
    Category,
    Collection,
    ColorVariant,
    Product,
    ProductSizeDescription,
    ProductSizeMeasurement,
    Size,
    VariantSize,
    VariantSizeDescription,
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
    assert "colors" not in created.json()  # variants have their own model permissions and endpoint

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
        "catalog.add_productsizedescription",
        "catalog.add_variantsizedescription",
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

    shared_description = client.post(
        "/api/admin/catalog/product-size-descriptions/",
        {"product": row.variant.product_id, "size": row.size_id, "description": "اندازه استاندارد"},
        content_type="application/json",
    )
    assert shared_description.status_code == 201, shared_description.content
    specific_description = client.post(
        "/api/admin/catalog/variant-size-descriptions/",
        {"variant_size": row.pk, "description": "برای این رنگ کمی آزادتر است"},
        content_type="application/json",
    )
    assert specific_description.status_code == 201, specific_description.content
    assert ProductSizeDescription.objects.count() == 1
    assert VariantSizeDescription.objects.count() == 1


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


def test_measurement_editor_requires_view_and_change_permissions(make_staff, make_variant_size):
    row = make_variant_size()
    measurement = ProductSizeMeasurement.objects.create(
        product=row.variant.product,
        size=row.size,
        name="عرض سینه",
        value="54",
        unit="سانتی‌متر",
        position=0,
    )
    description = ProductSizeDescription.objects.create(
        product=row.variant.product,
        size=row.size,
        description="اندازه استاندارد",
    )

    read_only = client_for(make_staff("catalog.view_productsizemeasurement"))
    assert read_only.get("/api/admin/catalog/product-measurements/").status_code == 200
    assert read_only.patch(
        f"/api/admin/catalog/product-measurements/{measurement.pk}/",
        {"value": "56"},
        content_type="application/json",
    ).status_code == 403

    editor = client_for(make_staff(
        "catalog.view_productsizemeasurement",
        "catalog.change_productsizemeasurement",
        "catalog.view_productsizedescription",
        "catalog.change_productsizedescription",
    ))
    changed = editor.patch(
        f"/api/admin/catalog/product-measurements/{measurement.pk}/",
        {"value": "56"},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    measurement.refresh_from_db()
    assert measurement.value == "56"

    changed_description = editor.patch(
        f"/api/admin/catalog/product-size-descriptions/{description.pk}/",
        {"description": "یک سایز آزادتر انتخاب کنید"},
        content_type="application/json",
    )
    assert changed_description.status_code == 200, changed_description.content
    description.refresh_from_db()
    assert description.description == "یک سایز آزادتر انتخاب کنید"


def test_inventory_history_can_be_filtered_to_one_variant_size_and_shows_actor(make_staff, make_variant_size):
    first = make_variant_size(stock=3)
    second = make_variant_size(stock=8)
    actor = make_staff("inventory.add_inventoryadjustment", "inventory.view_inventoryadjustment", "catalog.view_variantsize")
    client = client_for(actor)
    client.post(
        "/api/admin/inventory/adjustments/",
        {"variant_size": first.pk, "quantity_change": 2, "reason": "ورود بار"},
        content_type="application/json",
    )
    client.post(
        "/api/admin/inventory/adjustments/",
        {"variant_size": second.pk, "quantity_change": -1, "reason": "اصلاح شمارش"},
        content_type="application/json",
    )

    response = client.get(f"/api/admin/inventory/adjustments/?variant_size={first.pk}")
    assert response.status_code == 200, response.content
    payload = response.json()
    results = payload["results"] if isinstance(payload, dict) else payload
    assert len(results) == 1
    assert results[0]["variant_size"] == first.pk
    assert results[0]["quantity_change"] == 2
    assert results[0]["created_by_label"] == actor.phone

    invalid = client.get("/api/admin/inventory/adjustments/?variant_size=not-a-number")
    assert invalid.status_code == 400



def test_catalog_taxonomy_create_update_and_safe_deactivation(make_staff):
    client = client_for(make_staff(
        "catalog.add_category", "catalog.view_category", "catalog.change_category",
        "catalog.add_collection", "catalog.view_collection", "catalog.change_collection",
        "catalog.add_size", "catalog.view_size", "catalog.change_size", "catalog.delete_size",
    ))

    category_response = client.post(
        "/api/admin/catalog/categories/",
        {"name": "لباس", "slug": "clothing", "position": 2},
        content_type="application/json",
    )
    assert category_response.status_code == 201, category_response.content
    category = Category.objects.get(pk=category_response.json()["id"])
    assert category.position == 2

    collection_response = client.post(
        "/api/admin/catalog/collections/",
        {"name": "پاییزه", "slug": "autumn", "position": 1},
        content_type="application/json",
    )
    assert collection_response.status_code == 201, collection_response.content
    collection = Collection.objects.get(pk=collection_response.json()["id"])

    category_update = client.patch(
        f"/api/admin/catalog/categories/{category.pk}/",
        {"is_active": False},
        content_type="application/json",
    )
    collection_update = client.patch(
        f"/api/admin/catalog/collections/{collection.pk}/",
        {"name": "مجموعه پاییز", "is_active": False},
        content_type="application/json",
    )
    assert category_update.status_code == 200, category_update.content
    assert collection_update.status_code == 200, collection_update.content
    category.refresh_from_db()
    collection.refresh_from_db()
    assert not category.is_active
    assert not collection.is_active

    size_response = client.post(
        "/api/admin/catalog/sizes/",
        {"code": "xxl", "label": "دو ایکس لارج", "position": 4},
        content_type="application/json",
    )
    assert size_response.status_code == 201, size_response.content
    size = Size.objects.get(pk=size_response.json()["id"])
    size_update = client.patch(
        f"/api/admin/catalog/sizes/{size.pk}/",
        {"label": "XXL"},
        content_type="application/json",
    )
    assert size_update.status_code == 200, size_update.content
    size.refresh_from_db()
    assert size.label == "XXL"
    assert client.delete(f"/api/admin/catalog/sizes/{size.pk}/").status_code == 405
    assert Size.objects.filter(pk=size.pk).exists()


def test_color_and_variant_size_can_be_updated_or_deactivated_without_stock_write(make_staff, make_variant_size):
    row = make_variant_size(stock=7)
    client = client_for(make_staff(
        "catalog.view_colorvariant", "catalog.change_colorvariant",
        "catalog.view_variantsize", "catalog.change_variantsize",
    ))

    color_response = client.patch(
        f"/api/admin/catalog/colors/{row.variant_id}/",
        {"name": "آبی جدید", "is_active": False},
        content_type="application/json",
    )
    assert color_response.status_code == 200, color_response.content
    row.variant.refresh_from_db()
    assert row.variant.name == "آبی جدید"
    assert not row.variant.is_active

    size_response = client.patch(
        f"/api/admin/catalog/variant-sizes/{row.pk}/",
        {"is_active": False, "stock_quantity": 999},
        content_type="application/json",
    )
    assert size_response.status_code == 200, size_response.content
    row.refresh_from_db()
    assert not row.is_active
    assert row.stock_quantity == 7



def test_variant_size_sku_can_be_updated_but_must_remain_unique(make_staff, make_variant_size):
    first = make_variant_size()
    second = make_variant_size()
    editor = client_for(make_staff("catalog.view_variantsize", "catalog.change_variantsize"))

    changed = editor.patch(
        f"/api/admin/catalog/variant-sizes/{first.pk}/",
        {"sku": "UPDATED-SKU-001"},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    first.refresh_from_db()
    assert first.sku == "UPDATED-SKU-001"
    assert changed.json()["sku"] == "UPDATED-SKU-001"

    duplicate = editor.patch(
        f"/api/admin/catalog/variant-sizes/{second.pk}/",
        {"sku": first.sku},
        content_type="application/json",
    )
    assert duplicate.status_code == 400
    second.refresh_from_db()
    assert second.sku != first.sku

    viewer = client_for(make_staff("catalog.view_variantsize"))
    denied = viewer.patch(
        f"/api/admin/catalog/variant-sizes/{second.pk}/",
        {"sku": "NO-WRITE"},
        content_type="application/json",
    )
    assert denied.status_code == 403


def test_color_variant_position_can_be_updated_and_negative_values_are_rejected(make_staff, make_variant_size):
    first_size = make_variant_size()
    first = first_size.variant
    first.position = 10
    first.save(update_fields=["position"])
    second = ColorVariant.objects.create(
        product=first.product,
        name="رنگ دوم",
        slug="second-color",
        hex_color="#123456",
        position=5,
    )
    editor = client_for(make_staff("catalog.view_colorvariant", "catalog.change_colorvariant"))

    changed = editor.patch(
        f"/api/admin/catalog/colors/{second.pk}/",
        {"position": 0},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    second.refresh_from_db()
    assert second.position == 0
    assert changed.json()["position"] == 0
    assert list(first.product.color_variants.values_list("id", flat=True)) == [second.pk, first.pk]

    invalid = editor.patch(
        f"/api/admin/catalog/colors/{first.pk}/",
        {"position": -1},
        content_type="application/json",
    )
    assert invalid.status_code == 400
    first.refresh_from_db()
    assert first.position == 10

def test_variant_size_description_requires_view_and_change_permissions(make_staff, make_variant_size):
    row = make_variant_size()
    description = VariantSizeDescription.objects.create(
        variant_size=row,
        description="برای این رنگ و سایز فیت آزادتر است",
    )

    no_access = client_for(make_staff())
    assert no_access.get("/api/admin/catalog/variant-size-descriptions/").status_code == 403

    viewer = client_for(make_staff("catalog.view_variantsizedescription"))
    assert viewer.get("/api/admin/catalog/variant-size-descriptions/").status_code == 200
    assert viewer.patch(
        f"/api/admin/catalog/variant-size-descriptions/{description.pk}/",
        {"description": "تغییر بدون مجوز"},
        content_type="application/json",
    ).status_code == 403

    editor = client_for(make_staff(
        "catalog.view_variantsizedescription",
        "catalog.change_variantsizedescription",
    ))
    changed = editor.patch(
        f"/api/admin/catalog/variant-size-descriptions/{description.pk}/",
        {"description": "توضیح اختصاصی ویرایش‌شده"},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    description.refresh_from_db()
    assert description.description == "توضیح اختصاصی ویرایش‌شده"
