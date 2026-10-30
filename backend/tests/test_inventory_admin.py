"""Inventory admin: stock is read-only in the catalog admin, adjustments go through the service, history is
append-only, and every action respects the per-model permissions."""

import pytest
from django.contrib.admin.models import LogEntry
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Size, VariantSize
from apps.inventory import services
from apps.inventory.models import InventoryAdjustment
from tests.conftest import client_for

pytestmark = pytest.mark.django_db

LIST = "/admin/inventory/inventoryadjustment/"
ADD = LIST + "add/"
ADD_PERM, VIEW_PERM = "inventory.add_inventoryadjustment", "inventory.view_inventoryadjustment"
PICKER_PERM = "catalog.view_variantsize"  # needed by the stock-item autocomplete


def stock(vs) -> int:
    return VariantSize.objects.values_list("stock_quantity", flat=True).get(pk=vs.pk)


def post_adjustment(client, vs, change="4", reason="Cycle count"):
    return client.post(ADD, {"variant_size": vs.pk, "quantity_change": change, "reason": reason})


@pytest.fixture
def operator(make_staff):
    """Staff who can create adjustments and read the history."""
    return make_staff(ADD_PERM, VIEW_PERM, PICKER_PERM)


# --- creating adjustments through the admin ---------------------------------------------------------
def test_staff_with_add_permission_can_add_stock(make_variant_size, operator):
    vs = make_variant_size(stock=5)
    response = post_adjustment(client_for(operator), vs, "4", "Delivery received")
    assert response.status_code == 302
    assert stock(vs) == 9
    record = InventoryAdjustment.objects.get()
    assert (record.variant_size, record.quantity_change, record.stock_after) == (vs, 4, 9)
    assert record.reason == "Delivery received" and record.created_by == operator


def test_staff_can_remove_stock(make_variant_size, operator):
    vs = make_variant_size(stock=5)
    assert post_adjustment(client_for(operator), vs, "-2", "Damaged").status_code == 302
    assert stock(vs) == 3 and InventoryAdjustment.objects.get().quantity_change == -2


def test_removing_more_than_available_is_a_form_error(make_variant_size, operator):
    vs = make_variant_size(stock=2)
    response = post_adjustment(client_for(operator), vs, "-5")
    assert response.status_code == 200 and b"only 2 in stock" in response.content
    assert stock(vs) == 2 and not InventoryAdjustment.objects.exists()


@pytest.mark.parametrize(
    "change, reason", [("0", "Recount"), ("5", ""), ("5", "   "), ("abc", "Recount"), ("", "Recount"), ("1.5", "x")]
)
def test_invalid_adjustment_forms_are_form_errors_not_500(make_variant_size, operator, change, reason):
    vs = make_variant_size(stock=2)
    response = post_adjustment(client_for(operator), vs, change, reason)
    assert response.status_code == 200
    assert stock(vs) == 2 and not InventoryAdjustment.objects.exists()


def test_adjustment_is_rejected_if_stock_changed_between_validation_and_save(
    make_variant_size, operator, monkeypatch
):
    vs = make_variant_size(stock=5)

    def lost_race(**kwargs):
        raise services.StockWouldGoNegative()

    monkeypatch.setattr("apps.inventory.admin.services.adjust_stock", lost_race)
    data = {"variant_size": vs.pk, "quantity_change": "1", "reason": "x"}
    response = client_for(operator).post(ADD, data, follow=True)
    assert response.status_code == 200 and b"would make stock negative" in response.content
    assert stock(vs) == 5 and not InventoryAdjustment.objects.exists()
    assert not LogEntry.objects.filter(content_type__app_label="inventory").exists()


def test_adding_page_can_be_prefilled_from_a_variant_size(make_variant_size, operator):
    vs = make_variant_size(stock=5)
    response = client_for(operator).get(ADD, {"variant_size": vs.pk})
    assert response.status_code == 200 and vs.sku.encode() in response.content


def test_stock_item_picker_works_for_authorized_staff_only(make_variant_size, make_staff):
    vs = make_variant_size(stock=5)
    params = {"term": vs.sku, "app_label": "inventory", "model_name": "inventoryadjustment", "field_name": "variant_size"}
    ok = client_for(make_staff(ADD_PERM, PICKER_PERM)).get("/admin/autocomplete/", params)
    assert ok.status_code == 200 and [r["id"] for r in ok.json()["results"]] == [str(vs.pk)]
    assert client_for(make_staff(ADD_PERM)).get("/admin/autocomplete/", params).status_code == 403


# --- history: who / why / when, read-only ----------------------------------------------------------------
def test_history_shows_who_what_why_and_when(make_variant_size, operator):
    vs = make_variant_size(stock=5)
    services.adjust_stock(variant_size_id=vs.pk, quantity_change=-2, reason="Water damage", created_by=operator)
    html = client_for(operator).get(LIST).content.decode()
    for expected in (vs.sku, "Water damage", operator.phone, "column-created_at", "column-created_by", "-2"):
        assert expected in html, expected


def test_history_can_be_searched_by_sku_and_reason(make_variant_size, operator):
    a, b = make_variant_size(stock=5), make_variant_size(stock=5)
    services.adjust_stock(variant_size_id=a.pk, quantity_change=1, reason="Found in backroom", created_by=operator)
    services.adjust_stock(variant_size_id=b.pk, quantity_change=1, reason="Supplier delivery", created_by=operator)
    client = client_for(operator)
    assert "1 inventory adjustment" in client.get(LIST, {"q": a.sku}).content.decode()
    assert "1 inventory adjustment" in client.get(LIST, {"q": "backroom"}).content.decode()


def test_detail_page_is_read_only(make_variant_size, operator):
    vs = make_variant_size(stock=5)
    record = services.adjust_stock(variant_size_id=vs.pk, quantity_change=1, reason="Recount", created_by=operator)
    response = client_for(operator).get(f"{LIST}{record.pk}/change/")
    html = response.content.decode()
    assert response.status_code == 200 and "Recount" in html
    for name in ("variant_size", "quantity_change", "reason", "stock_after"):
        assert f'name="{name}"' not in html


def test_history_cannot_be_changed_or_deleted_even_by_a_superuser(make_variant_size, su_client, superuser):
    vs = make_variant_size(stock=5)
    record = services.adjust_stock(variant_size_id=vs.pk, quantity_change=1, reason="Recount", created_by=superuser)
    url = f"{LIST}{record.pk}/"
    data = {"variant_size": vs.pk, "quantity_change": "99", "reason": "tampered"}
    assert su_client.post(url + "change/", data).status_code == 403
    assert su_client.get(url + "delete/").status_code == 403
    assert su_client.post(url + "delete/", {"post": "yes"}).status_code == 403
    record.refresh_from_db()
    assert (record.quantity_change, record.reason) == (1, "Recount") and stock(vs) == 6


def test_history_changelist_does_not_issue_per_row_queries(make_variant_size, operator, su_client):
    def populate(n):
        for _ in range(n):
            vs = make_variant_size(stock=5)
            services.adjust_stock(variant_size_id=vs.pk, quantity_change=1, reason="Count", created_by=operator)

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert su_client.get(LIST).status_code == 200
        return len(ctx)

    populate(2)
    small = count()
    populate(8)
    assert count() == small


# --- permissions ---------------------------------------------------------------------------------------------
def test_customers_and_anonymous_users_cannot_reach_inventory(make_variant_size, customer_client, client):
    vs = make_variant_size(stock=5)
    for c in (customer_client, client):
        assert c.get(LIST).status_code == 302 and "/admin/login/" in c.get(LIST)["Location"]
        assert post_adjustment(c, vs).status_code == 302
    assert stock(vs) == 5 and not InventoryAdjustment.objects.exists()


def test_staff_without_inventory_permissions_are_refused(make_variant_size, make_staff):
    vs = make_variant_size(stock=5)
    client = client_for(make_staff("catalog.view_variantsize", "catalog.change_variantsize"))
    assert client.get(LIST).status_code == 403
    assert client.get(ADD).status_code == 403
    assert post_adjustment(client, vs).status_code == 403
    assert stock(vs) == 5 and not InventoryAdjustment.objects.exists()


def test_view_only_staff_can_read_but_not_create(make_variant_size, make_staff):
    vs = make_variant_size(stock=5)
    client = client_for(make_staff(VIEW_PERM))
    assert client.get(LIST).status_code == 200
    assert client.get(ADD).status_code == 403
    assert post_adjustment(client, vs).status_code == 403
    assert stock(vs) == 5 and not InventoryAdjustment.objects.exists()


def test_add_permission_alone_does_not_expose_the_history(make_variant_size, make_staff):
    vs = make_variant_size(stock=5)
    client = client_for(make_staff(ADD_PERM, PICKER_PERM))
    assert client.get(LIST).status_code == 403
    assert post_adjustment(client, vs).status_code == 302  # creating is allowed
    assert stock(vs) == 9


# --- catalog admin: stock is no longer directly editable ------------------------------------------------------
def _formset(prefix, total=0, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total), f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def _variant_page_data(vs, extra_sizes=(), **overrides):
    variant, image = vs.variant, vs.variant.images.get()
    data = {
        "product": variant.product_id, "name": variant.name, "slug": variant.slug, "hex_color": variant.hex_color,
        "position": variant.position, "is_active": "on",
        **_formset("sizes", total=1 + len(extra_sizes), initial=1),
        "sizes-0-id": vs.pk, "sizes-0-variant": variant.pk, "sizes-0-size": vs.size_id, "sizes-0-sku": vs.sku,
        "sizes-0-is_active": "on",
        **_formset("images", total=1, initial=1),
        "images-0-id": image.pk, "images-0-variant": variant.pk, "images-0-storage_key": image.storage_key,
        "images-0-position": "0", "images-0-is_primary": "on", "images-0-width": "10", "images-0-height": "10",
        "images-0-content_type": "image/webp", "images-0-is_active": "on",
    }
    for index, (size, sku, posted_stock) in enumerate(extra_sizes, start=1):
        data.update({
            f"sizes-{index}-id": "", f"sizes-{index}-variant": variant.pk, f"sizes-{index}-size": size.pk,
            f"sizes-{index}-sku": sku, f"sizes-{index}-stock_quantity": posted_stock, f"sizes-{index}-is_active": "on",
        })
    data.update(overrides)
    return data


def test_size_inline_shows_stock_read_only(make_variant_size, su_client):
    vs = make_variant_size(stock=5)
    html = su_client.get(f"/admin/catalog/colorvariant/{vs.variant_id}/change/").content.decode()
    assert 'name="sizes-0-stock_quantity"' not in html
    assert "field-stock_quantity" in html


def test_posting_stock_through_the_size_inline_is_ignored(make_variant_size, su_client):
    vs = make_variant_size(stock=5)
    data = _variant_page_data(vs, **{"sizes-0-stock_quantity": "999", "sizes-0-sku": "RENAMED-SKU"})
    assert su_client.post(f"/admin/catalog/colorvariant/{vs.variant_id}/change/", data).status_code == 302
    vs.refresh_from_db()
    assert vs.sku == "RENAMED-SKU"  # legitimate size management still works
    assert vs.stock_quantity == 5  # the injected stock value did not


def test_new_size_added_through_the_inline_starts_at_zero_stock(make_variant_size, su_client):
    vs = make_variant_size(stock=5)
    other = Size.objects.create(code="xl", label="XL")
    data = _variant_page_data(vs, extra_sizes=[(other, "INLINE-NEW", "7")])
    assert su_client.post(f"/admin/catalog/colorvariant/{vs.variant_id}/change/", data).status_code == 302
    assert VariantSize.objects.get(sku="INLINE-NEW").stock_quantity == 0


def test_variant_size_page_has_no_editable_stock_field(make_variant_size, su_client):
    vs = make_variant_size(stock=5)
    html = su_client.get(f"/admin/catalog/variantsize/{vs.pk}/change/").content.decode()
    assert 'name="stock_quantity"' not in html
    assert "field-stock_quantity" in html and "Adjust stock (add or remove units)" in html
    assert f"/admin/inventory/inventoryadjustment/add/?variant_size={vs.pk}" in html


def test_adjust_stock_link_is_only_shown_to_staff_who_can_use_it(make_variant_size, make_staff):
    vs = make_variant_size(stock=5)
    staff = make_staff("catalog.view_variantsize", "catalog.change_variantsize")
    html = client_for(staff).get(f"/admin/catalog/variantsize/{vs.pk}/change/").content.decode()
    assert "Adjust stock" not in html and "field-stock_quantity" in html


def test_posting_stock_to_the_variant_size_page_is_ignored(make_variant_size, su_client):
    vs = make_variant_size(stock=5)
    data = {"variant": vs.variant_id, "size": vs.size_id, "sku": "RENAMED-2", "stock_quantity": "999", **_formset("description")}  # inactive
    assert su_client.post(f"/admin/catalog/variantsize/{vs.pk}/change/", data).status_code == 302
    vs.refresh_from_db()
    assert (vs.sku, vs.is_active, vs.stock_quantity) == ("RENAMED-2", False, 5)  # management works, stock untouched


def test_variant_size_created_on_its_own_page_starts_at_zero_stock(make_variant_size, su_client):
    vs = make_variant_size(stock=5)
    other = Size.objects.create(code="l", label="L")
    data = {"variant": vs.variant_id, "size": other.pk, "sku": "ADD-PAGE-1", "is_active": "on", "stock_quantity": "50", **_formset("description")}
    assert su_client.post("/admin/catalog/variantsize/add/", data).status_code == 302
    assert VariantSize.objects.get(sku="ADD-PAGE-1").stock_quantity == 0


def test_variant_size_changelist_has_no_editable_stock_column(make_variant_size, su_client):
    make_variant_size(stock=5)
    html = su_client.get("/admin/catalog/variantsize/").content.decode()
    assert 'name="form-0-stock_quantity"' not in html and "field-stock_quantity" in html
