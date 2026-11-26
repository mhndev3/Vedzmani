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


def test_product_edit_rejects_invalid_discount_for_effective_price(make_staff):
    category = Category.objects.create(name="لباس", slug="clothing")
    product = Product.objects.create(
        category=category,
        name="بافت",
        slug="basic-knit",
        price=Decimal("1250000"),
        sale_price=Decimal("1100000"),
    )
    client = client_for(make_staff("catalog.view_product", "catalog.change_product"))
    url = f"/api/admin/catalog/products/{product.pk}/"

    invalid_discount = client.patch(
        url, {"sale_price": "1250000"}, content_type="application/json"
    )
    assert invalid_discount.status_code == 400
    product.refresh_from_db()
    assert product.price == Decimal("1250000")
    assert product.sale_price == Decimal("1100000")

    invalid_base_price = client.patch(
        url, {"price": "1000000"}, content_type="application/json"
    )
    assert invalid_base_price.status_code == 400
    product.refresh_from_db()
    assert product.price == Decimal("1250000")
    assert product.sale_price == Decimal("1100000")

    cleared_discount = client.patch(
        url, {"sale_price": None}, content_type="application/json"
    )
    assert cleared_discount.status_code == 200, cleared_discount.content
    product.refresh_from_db()
    assert product.sale_price is None

    valid_discount = client.patch(
        url, {"price": "1300000", "sale_price": "1200000"},
        content_type="application/json",
    )
    assert valid_discount.status_code == 200, valid_discount.content
    product.refresh_from_db()
    assert product.price == Decimal("1300000")
    assert product.sale_price == Decimal("1200000")


def test_product_category_change_preserves_attributes_from_previous_category(make_staff):
    old_category = Category.objects.create(
        name="لباس قدیمی",
        slug="legacy-clothing",
        product_fields=[{
            "key": "fabric",
            "label": "جنس پارچه",
            "type": "text",
            "unit": "",
            "required": False,
        }],
    )
    new_category = Category.objects.create(
        name="لباس جدید",
        slug="new-clothing",
        product_fields=[{
            "key": "fit",
            "label": "نوع فیت",
            "type": "text",
            "unit": "",
            "required": False,
        }],
    )
    product = Product.objects.create(
        category=old_category,
        name="بافت",
        slug="legacy-attribute-knit",
        price=Decimal("1000000"),
        attributes={"fabric": "پنبه"},
    )
    client = client_for(make_staff("catalog.view_product", "catalog.change_product"))

    response = client.patch(
        f"/api/admin/catalog/products/{product.pk}/",
        {"category": new_category.pk, "attributes": {"fit": "آزاد"}},
        content_type="application/json",
    )

    assert response.status_code == 200, response.content
    product.refresh_from_db()
    assert product.category_id == new_category.pk
    assert product.attributes == {"fit": "آزاد", "fabric": "پنبه"}


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

    auto_slug = client.post(
        "/api/admin/catalog/colors/",
        {"product": product.pk, "name": "سبز", "hex_color": "#228B22"},
        content_type="application/json",
    )
    assert auto_slug.status_code == 201, auto_slug.content
    assert auto_slug.json()["slug"].startswith("color-")

    size_response = client.post(
        "/api/admin/catalog/variant-sizes/",
        {"variant": color_data["id"], "size": size.pk, "sku": "KNIT-SKY-M", "stock_quantity": 99},
        content_type="application/json",
    )
    assert size_response.status_code == 201, size_response.content
    row = VariantSize.objects.get(sku="KNIT-SKY-M")
    assert row.stock_quantity == 0
    assert size_response.json()["stock_quantity"] == 0

    # Adding a size later through the admin catalog does not require a technical SKU.
    extra_size = Size.objects.create(code="l", label="بزرگ")
    generated = client.post(
        "/api/admin/catalog/variant-sizes/",
        {"variant": color_data["id"], "size": extra_size.pk, "stock_quantity": 42},
        content_type="application/json",
    )
    assert generated.status_code == 201, generated.content
    generated_row = VariantSize.objects.get(pk=generated.json()["id"])
    assert generated_row.sku == f"VZ-{product.pk}-{color_data['id']}-{extra_size.pk}"
    assert generated_row.stock_quantity == 0
    assert generated.json()["stock_quantity"] == 0


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


def test_measurement_rows_can_be_reordered_with_change_permission_only(make_staff, make_variant_size):
    variant_size = make_variant_size()
    product = variant_size.variant.product

    shared_first = ProductSizeMeasurement.objects.create(
        product=product, size=variant_size.size, name="عرض سینه", value="50", position=0
    )
    shared_second = ProductSizeMeasurement.objects.create(
        product=product, size=variant_size.size, name="قد لباس", value="60", position=1
    )
    specific_first = VariantSizeMeasurement.objects.create(
        variant_size=variant_size, name="دور کمر", value="45", position=0
    )
    specific_second = VariantSizeMeasurement.objects.create(
        variant_size=variant_size, name="قد آستین", value="55", position=1
    )

    editor = client_for(make_staff(
        "catalog.change_productsizemeasurement",
        "catalog.change_variantsizemeasurement",
    ))
    shared = editor.post(
        "/api/admin/catalog/product-measurements/reorder/",
        {
            "product": product.pk,
            "size": variant_size.size_id,
            "measurement_ids": [shared_second.pk, shared_first.pk],
        },
        content_type="application/json",
    )
    assert shared.status_code == 200, shared.content
    assert list(
        ProductSizeMeasurement.objects.filter(product=product, size=variant_size.size)
        .order_by("position").values_list("id", flat=True)
    ) == [shared_second.pk, shared_first.pk]

    specific = editor.post(
        "/api/admin/catalog/variant-size-measurements/reorder/",
        {
            "variant_size": variant_size.pk,
            "measurement_ids": [specific_second.pk, specific_first.pk],
        },
        content_type="application/json",
    )
    assert specific.status_code == 200, specific.content
    assert list(
        VariantSizeMeasurement.objects.filter(variant_size=variant_size)
        .order_by("position").values_list("id", flat=True)
    ) == [specific_second.pk, specific_first.pk]

    # Partial lists cannot silently hide or discard existing rows.
    invalid = editor.post(
        "/api/admin/catalog/product-measurements/reorder/",
        {
            "product": product.pk,
            "size": variant_size.size_id,
            "measurement_ids": [shared_first.pk],
        },
        content_type="application/json",
    )
    assert invalid.status_code == 400
    assert list(
        ProductSizeMeasurement.objects.filter(product=product, size=variant_size.size)
        .order_by("position").values_list("id", flat=True)
    ) == [shared_second.pk, shared_first.pk]

    viewer = client_for(make_staff("catalog.view_productsizemeasurement"))
    denied = viewer.post(
        "/api/admin/catalog/product-measurements/reorder/",
        {
            "product": product.pk,
            "size": variant_size.size_id,
            "measurement_ids": [shared_first.pk, shared_second.pk],
        },
        content_type="application/json",
    )
    assert denied.status_code == 403


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




def test_taxonomy_ordering_is_atomic_and_requires_change_permission(make_staff):
    category_first = Category.objects.create(name="اول", slug="first", position=0)
    category_second = Category.objects.create(name="دوم", slug="second", position=1)
    collection_first = Collection.objects.create(name="تابستان", slug="summer", position=0)
    collection_second = Collection.objects.create(name="زمستان", slug="winter", position=1)

    editor = client_for(make_staff("catalog.change_category", "catalog.change_collection"))
    category_ids = list(Category.objects.order_by("position", "id").values_list("id", flat=True))
    category_first_index = category_ids.index(category_first.pk)
    category_second_index = category_ids.index(category_second.pk)
    category_ids[category_first_index], category_ids[category_second_index] = (
        category_ids[category_second_index], category_ids[category_first_index]
    )
    category_response = editor.post(
        "/api/admin/catalog/categories/reorder/",
        {"entry_ids": category_ids},
        content_type="application/json",
    )
    assert category_response.status_code == 200, category_response.content
    assert list(Category.objects.order_by("position", "id").values_list("id", flat=True)) == category_ids

    collection_ids = list(Collection.objects.order_by("position", "id").values_list("id", flat=True))
    collection_first_index = collection_ids.index(collection_first.pk)
    collection_second_index = collection_ids.index(collection_second.pk)
    collection_ids[collection_first_index], collection_ids[collection_second_index] = (
        collection_ids[collection_second_index], collection_ids[collection_first_index]
    )
    collection_response = editor.post(
        "/api/admin/catalog/collections/reorder/",
        {"entry_ids": collection_ids},
        content_type="application/json",
    )
    assert collection_response.status_code == 200, collection_response.content
    assert list(Collection.objects.order_by("position", "id").values_list("id", flat=True)) == collection_ids

    invalid = editor.post(
        "/api/admin/catalog/categories/reorder/",
        {"entry_ids": [category_first.pk]},
        content_type="application/json",
    )
    assert invalid.status_code == 400
    assert list(Category.objects.order_by("position", "id").values_list("id", flat=True)) == category_ids

    viewer = client_for(make_staff("catalog.view_category"))
    denied = viewer.post(
        "/api/admin/catalog/categories/reorder/",
        {"entry_ids": [category_first.pk, category_second.pk]},
        content_type="application/json",
    )
    assert denied.status_code == 403


def test_color_variant_ordering_is_atomic_and_scoped_to_one_product(make_staff):
    category = Category.objects.create(name="لباس", slug="color-order-category")
    first_product = Product.objects.create(
        category=category, name="محصول اول", slug="color-order-first", price=1000
    )
    second_product = Product.objects.create(
        category=category, name="محصول دوم", slug="color-order-second", price=1000
    )
    first = ColorVariant.objects.create(
        product=first_product, name="مشکی", slug="black", position=0
    )
    second = ColorVariant.objects.create(
        product=first_product, name="سفید", slug="white", position=1
    )
    unrelated = ColorVariant.objects.create(
        product=second_product, name="آبی", slug="blue", position=0
    )

    editor = client_for(make_staff("catalog.change_colorvariant"))
    response = editor.post(
        "/api/admin/catalog/colors/reorder/",
        {"product": first_product.pk, "entry_ids": [second.pk, first.pk]},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    assert list(
        ColorVariant.objects.filter(product=first_product).order_by("position", "id").values_list("id", flat=True)
    ) == [second.pk, first.pk]
    unrelated.refresh_from_db()
    assert unrelated.position == 0

    incomplete = editor.post(
        "/api/admin/catalog/colors/reorder/",
        {"product": first_product.pk, "entry_ids": [first.pk]},
        content_type="application/json",
    )
    assert incomplete.status_code == 400
    assert list(
        ColorVariant.objects.filter(product=first_product).order_by("position", "id").values_list("id", flat=True)
    ) == [second.pk, first.pk]

    viewer = client_for(make_staff("catalog.view_colorvariant"))
    denied = viewer.post(
        "/api/admin/catalog/colors/reorder/",
        {"product": first_product.pk, "entry_ids": [first.pk, second.pk]},
        content_type="application/json",
    )
    assert denied.status_code == 403


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

    # A store manager can create a size with only its customer-facing label.
    # The backend generates its internal code and later label edits preserve it.
    generated_response = client.post(
        "/api/admin/catalog/sizes/",
        {"label": "دو ایکس لارج پلاس", "position": 5},
        content_type="application/json",
    )
    assert generated_response.status_code == 201, generated_response.content
    generated_size = Size.objects.get(pk=generated_response.json()["id"])
    generated_code = generated_size.code
    assert generated_code.startswith("size-")
    assert len(generated_code) <= 20
    generated_update = client.patch(
        f"/api/admin/catalog/sizes/{generated_size.pk}/",
        {"label": "XXL Plus"},
        content_type="application/json",
    )
    assert generated_update.status_code == 200, generated_update.content
    generated_size.refresh_from_db()
    assert generated_size.code == generated_code
    assert generated_size.label == "XXL Plus"

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

    # An empty override removes the color/size-specific text so the public serializer
    # can fall back to the shared product/size description.
    cleared = editor.patch(
        f"/api/admin/catalog/variant-size-descriptions/{description.pk}/",
        {"description": ""},
        content_type="application/json",
    )
    assert cleared.status_code == 200, cleared.content
    description.refresh_from_db()
    assert description.description == ""


def test_category_creation_preserves_existing_categories_and_size_assignments(make_staff):
    sizes = [
        Size.objects.create(code="m", label="متوسط"),
        Size.objects.create(code="l", label="بزرگ"),
    ]
    client = client_for(make_staff(
        "catalog.add_category", "catalog.view_category", "catalog.change_category",
    ))

    first = client.post(
        "/api/admin/catalog/categories/",
        {"name": "شلوار آزمایشی", "slug": "test-category-trousers-size-map", "size_ids": [sizes[0].pk]},
        content_type="application/json",
    )
    assert first.status_code == 201, first.content
    second = client.post(
        "/api/admin/catalog/categories/",
        {"name": "پیراهن آزمایشی", "slug": "test-category-shirts-size-map", "size_ids": [sizes[1].pk]},
        content_type="application/json",
    )
    assert second.status_code == 201, second.content

    listed = client.get("/api/admin/catalog/categories/")
    assert listed.status_code == 200
    rows = listed.json()["results"]
    assert {row["slug"] for row in rows} >= {"test-category-trousers-size-map", "test-category-shirts-size-map"}
    assert set(next(row for row in rows if row["slug"] == "test-category-trousers-size-map")["sizes"]) == {sizes[0].pk}
    assert set(next(row for row in rows if row["slug"] == "test-category-shirts-size-map")["sizes"]) == {sizes[1].pk}

    category_id = first.json()["id"]
    unchanged = client.patch(
        f"/api/admin/catalog/categories/{category_id}/",
        {"name": "شلوار روزمره"},
        content_type="application/json",
    )
    assert unchanged.status_code == 200, unchanged.content
    assert set(unchanged.json()["sizes"]) == {sizes[0].pk}
    assert Category.objects.filter(pk__in=[first.json()["id"], second.json()["id"]]).count() == 2


def test_product_workspace_save_updates_product_color_sku_and_audited_stock_atomically(make_staff, make_variant_size):
    row = make_variant_size(stock=4)
    product = row.variant.product
    actor = make_staff(
        "catalog.change_product",
        "catalog.change_colorvariant",
        "catalog.change_variantsize",
        "inventory.add_inventoryadjustment",
        "catalog.view_variantsize",
    )
    client = client_for(actor)

    response = client.post(
        f"/api/admin/catalog/products/{product.pk}/workspace-save/",
        {
            "product": {"name": "بافت ویرایش‌شده"},
            "colors": [{"id": row.variant_id, "name": "آبی روشن", "hex_color": "#87CEEB"}],
            "variant_sizes": [{
                "id": row.pk,
                "sku": "WORKSPACE-SKU",
                "quantity_change": 3,
                "stock_reason": "ثبت موجودی اولیه",
            }],
        },
        content_type="application/json",
    )

    assert response.status_code == 200, response.content
    product.refresh_from_db()
    row.refresh_from_db()
    assert product.name == "بافت ویرایش‌شده"
    assert ColorVariant.objects.get(pk=row.variant_id).name == "آبی روشن"
    assert row.sku == "WORKSPACE-SKU"
    assert row.stock_quantity == 7
    adjustment = InventoryAdjustment.objects.get()
    assert adjustment.created_by == actor
    assert adjustment.quantity_change == 3
    assert adjustment.stock_after == 7


def test_product_workspace_save_creates_color_sizes_and_audited_initial_stock(make_staff, make_variant_size):
    existing = make_variant_size(stock=0)
    product = existing.variant.product
    product.category.sizes.add(existing.size)
    actor = make_staff(
        "catalog.change_product",
        "catalog.add_colorvariant",
        "catalog.add_variantsize",
        "inventory.add_inventoryadjustment",
        "catalog.view_variantsize",
    )
    client = client_for(actor)

    response = client.post(
        f"/api/admin/catalog/products/{product.pk}/workspace-save/",
        {
            "new_colors": [{
                "name": "سبز",
                "hex_color": "#008000",
                "sizes": [{"size": existing.size_id, "initial_stock": 5}],
            }],
        },
        content_type="application/json",
    )

    assert response.status_code == 200, response.content
    created_color = ColorVariant.objects.get(product=product, name="سبز")
    created_size = VariantSize.objects.get(variant=created_color, size=existing.size)
    assert created_color.product_code
    assert created_size.stock_quantity == 5
    adjustment = InventoryAdjustment.objects.get(variant_size=created_size)
    assert adjustment.quantity_change == 5
    assert adjustment.stock_after == 5
    assert adjustment.created_by == actor


def test_product_workspace_save_rolls_back_new_color_when_initial_stock_fails(make_staff, make_variant_size):
    existing = make_variant_size(stock=0)
    product = existing.variant.product
    product.category.sizes.add(existing.size)
    client = client_for(make_staff(
        "catalog.change_product",
        "catalog.add_colorvariant",
        "catalog.add_variantsize",
        "inventory.add_inventoryadjustment",
        "catalog.view_variantsize",
    ))

    response = client.post(
        f"/api/admin/catalog/products/{product.pk}/workspace-save/",
        {
            "new_colors": [{
                "name": "نباید باقی بماند",
                "hex_color": "#008000",
                "sizes": [{"size": existing.size_id, "initial_stock": -1}],
            }],
        },
        content_type="application/json",
    )

    assert response.status_code == 400, response.content
    assert not ColorVariant.objects.filter(product=product, name="نباید باقی بماند").exists()


def test_product_workspace_save_rolls_back_product_and_stock_when_adjustment_fails(make_staff, make_variant_size):
    row = make_variant_size(stock=2)
    product = row.variant.product
    client = client_for(make_staff(
        "catalog.change_product",
        "catalog.change_variantsize",
        "inventory.add_inventoryadjustment",
        "catalog.view_variantsize",
    ))

    response = client.post(
        f"/api/admin/catalog/products/{product.pk}/workspace-save/",
        {
            "product": {"name": "نباید ذخیره شود"},
            "variant_sizes": [{
                "id": row.pk,
                "quantity_change": -3,
                "stock_reason": "اصلاح شمارش",
            }],
        },
        content_type="application/json",
    )

    assert response.status_code == 409, response.content
    product.refresh_from_db()
    row.refresh_from_db()
    assert product.name != "نباید ذخیره شود"
    assert row.stock_quantity == 2
    assert not InventoryAdjustment.objects.exists()


def test_product_workspace_save_requires_permissions_for_every_submitted_section(make_staff, make_variant_size):
    row = make_variant_size(stock=2)
    product = row.variant.product
    client = client_for(make_staff("catalog.change_product"))

    response = client.post(
        f"/api/admin/catalog/products/{product.pk}/workspace-save/",
        {
            "product": {"name": "نباید تغییر کند"},
            "variant_sizes": [{"id": row.pk, "sku": "NO-PERMISSION"}],
        },
        content_type="application/json",
    )

    assert response.status_code == 403
    product.refresh_from_db()
    row.refresh_from_db()
    assert product.name != "نباید تغییر کند"
    assert row.sku != "NO-PERMISSION"


def test_product_publication_can_be_toggled_without_mutating_children_and_requires_change_permission(
    make_staff, make_variant_size
):
    row = make_variant_size(stock=7)
    product = row.variant.product
    product.is_active = False
    product.save(update_fields=["is_active"])

    editor = client_for(make_staff("catalog.view_product", "catalog.change_product"))
    published = editor.patch(
        f"/api/admin/catalog/products/{product.pk}/",
        {"is_active": True},
        content_type="application/json",
    )
    assert published.status_code == 200, published.content
    product.refresh_from_db()
    row.refresh_from_db()
    assert product.is_active is True
    assert row.stock_quantity == 7
    assert row.is_active is True
    assert row.variant.is_active is True

    unpublished = editor.patch(
        f"/api/admin/catalog/products/{product.pk}/",
        {"is_active": False},
        content_type="application/json",
    )
    assert unpublished.status_code == 200, unpublished.content
    product.refresh_from_db()
    row.refresh_from_db()
    assert product.is_active is False
    assert row.stock_quantity == 7
    assert row.is_active is True
    assert row.variant.is_active is True

    viewer = client_for(make_staff("catalog.view_product"))
    denied = viewer.patch(
        f"/api/admin/catalog/products/{product.pk}/",
        {"is_active": True},
        content_type="application/json",
    )
    assert denied.status_code == 403
    product.refresh_from_db()
    assert product.is_active is False
    assert row.stock_quantity == 7
