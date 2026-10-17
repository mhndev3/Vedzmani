"""Order admin: strictly read-only, PII behind `orders.view_order_pii`, bounded query count.

Test rows are created through the ORM (the checkout API is covered elsewhere). Full values that must never reach an
unauthorized page are deliberately unusual strings so a substring check cannot match by accident.
"""

from decimal import Decimal

from urllib.parse import quote, quote_plus

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils.html import escape

from apps.accounts.models import User
from apps.orders.admin import OrderAdmin, OrderItemAdmin, OrderItemInline
from apps.orders.models import Order, OrderItem
from apps.orders.permissions import PII_PERMISSION, create_order_pii_permission, mask_phone

from tests.conftest import client_for, new_phone

pytestmark = pytest.mark.django_db

FULL_PHONE = "+989123456789"
MASKED_PHONE = "+9891****789"
RECIPIENT = "Zhaleh Recipient-Q"
PROVINCE = "Zanjan-Province-Q"
CITY = "Abhar-City-Q"
ADDRESS = "No. 77 Quince Alley Q"
POSTAL = "4567891230"
PII_VALUES = (FULL_PHONE, "989123456789", "09123456789", RECIPIENT, PROVINCE, CITY, ADDRESS, POSTAL)

VIEW = ("orders.view_order", "orders.view_orderitem")


def make_order(make_variant_size, *, phone=FULL_PHONE, items=1, user=None, **overrides):
    user = user or User.objects.create_user(new_phone())
    values = {
        "user": user, "customer_phone": phone, "recipient_name": RECIPIENT, "province": PROVINCE, "city": CITY,
        "address": ADDRESS, "postal_code": POSTAL, "total": Decimal("2000") * items,
    }
    values.update(overrides)
    order = Order.objects.create(**values)
    for _ in range(items):
        vs = make_variant_size(stock=5)
        OrderItem.objects.create(
            order=order, variant_size=vs, product_name=vs.variant.product.name, color_name="Black",
            size_label="M", sku=vs.sku, unit_price=Decimal("2000"), quantity=1, subtotal=Decimal("2000"),
        )
    return order


@pytest.fixture
def order(make_variant_size):
    return make_order(make_variant_size)


@pytest.fixture
def staff_client(make_staff):
    return client_for(make_staff(*VIEW))


@pytest.fixture
def pii_client(make_staff):
    return client_for(make_staff(*VIEW, PII_PERMISSION))


def assert_no_pii(response, *, echoed_query=None):
    """No protected value may appear in the page.

    `echoed_query` is the search term the *requester* typed: Django reflects it in the search box and in `q=` link
    parameters. That is the caller's own input, not stored data, so exactly those reflections are removed first.
    Anything else on the page (rows, filters, other fields) is still checked, and the search tests also assert that
    zero rows came back.
    """
    body = response.content.decode()
    if echoed_query:
        for variant in {escape(echoed_query), quote(echoed_query, safe=""), quote_plus(echoed_query)}:
            body = body.replace(f'value="{variant}"', "").replace(f"q={variant}", "")
    for value in PII_VALUES:
        assert value not in body, f"leaked {value!r}"


def snapshot(order):
    order.refresh_from_db()
    return (
        order.status, order.payment_status, order.customer_phone, order.recipient_name, order.address, order.total,
        list(order.items.values_list("id", "quantity", "subtotal")),
    )


def site_admin(model):
    return django_admin.site._registry[model]


def request_for(user):
    request = RequestFactory().get("/admin/")
    request.user = user
    return request


# --- permission registration ----------------------------------------------------------------------------------
def test_pii_permission_exists_after_migrate_and_is_not_granted_by_default(order, make_staff):
    perm = Permission.objects.get(content_type__app_label="orders", codename="view_order_pii")
    assert perm.content_type.model == "order"
    assert not perm.user_set.exists() and not perm.group_set.exists()
    assert not make_staff(*VIEW).has_perm(PII_PERMISSION)


def test_permission_registration_is_idempotent():
    create_order_pii_permission(sender=None)
    create_order_pii_permission(sender=None)
    assert Permission.objects.filter(content_type__app_label="orders", codename="view_order_pii").count() == 1


def test_no_model_migration_is_needed():
    call_command("makemigrations", "orders", "--check", "--dry-run", verbosity=0)  # SystemExit(1) on drift


def test_superuser_holds_pii_permission_by_django_convention_staff_do_not(superuser, make_staff):
    assert superuser.has_perm(PII_PERMISSION)
    assert not make_staff("orders.view_order").has_perm(PII_PERMISSION)


# --- authentication and access --------------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/admin/orders/order/", "/admin/orders/orderitem/", "/admin/orders/order/1/change/"])
def test_anonymous_is_redirected_to_admin_login(client, path):
    response = client.get(path)
    assert response.status_code == 302 and response["Location"].startswith("/admin/login/")


def test_customer_without_staff_flag_cannot_enter(customer_client):
    response = customer_client.get("/admin/orders/order/")
    assert response.status_code == 302 and response["Location"].startswith("/admin/login/")


def test_staff_without_order_permissions_is_forbidden(make_staff, order):
    client = client_for(make_staff())
    assert client.get("/admin/orders/order/").status_code == 403
    assert client.get(f"/admin/orders/order/{order.pk}/change/").status_code == 403
    assert client.get("/admin/orders/orderitem/").status_code == 403


def test_change_permission_does_not_imply_view(make_staff, order):
    client = client_for(make_staff("orders.change_order", "orders.change_orderitem"))
    assert client.get("/admin/orders/order/").status_code == 403
    assert client.get(f"/admin/orders/order/{order.pk}/change/").status_code == 403
    assert client.get("/admin/orders/orderitem/").status_code == 403


def test_pii_permission_alone_does_not_open_the_pages(make_staff, order):
    client = client_for(make_staff(PII_PERMISSION))
    assert client.get("/admin/orders/order/").status_code == 403
    assert client.get(f"/admin/orders/order/{order.pk}/change/").status_code == 403


def test_staff_with_view_permissions_see_list_and_detail(staff_client, order):
    listing = staff_client.get("/admin/orders/order/")
    assert listing.status_code == 200
    html = listing.content.decode()
    assert f">{order.pk}</a>" in html and "Pending" in html and "Unpaid" in html and "2000" in html
    assert staff_client.get(f"/admin/orders/order/{order.pk}/change/").status_code == 200


# --- PII: list, detail, direct URL ----------------------------------------------------------------------------
def test_list_masks_phone_for_everyone_even_with_pii_permission(staff_client, pii_client, su_client, order):
    for client in (staff_client, pii_client, su_client):
        html = client.get("/admin/orders/order/").content.decode()
        assert MASKED_PHONE in html
        assert_no_pii(client.get("/admin/orders/order/"))


def test_detail_without_pii_permission_shows_masked_phone_and_no_delivery_data(staff_client, order):
    response = staff_client.get(f"/admin/orders/order/{order.pk}/change/")
    assert response.status_code == 200
    assert MASKED_PHONE in response.content.decode()
    assert "view order PII" in response.content.decode()
    assert_no_pii(response)


def test_detail_with_pii_permission_shows_all_protected_fields(pii_client, order):
    html = pii_client.get(f"/admin/orders/order/{order.pk}/change/").content.decode()
    for value in (FULL_PHONE, RECIPIENT, PROVINCE, CITY, ADDRESS, POSTAL):
        assert value in html


def test_detail_url_variants_cannot_bypass_the_permission(staff_client, order):
    base = f"/admin/orders/order/{order.pk}/change/"
    for suffix in ("?pii=1", "?view_order_pii=true", "?_popup=1", "?fields=customer_phone,address"):
        response = staff_client.get(base + suffix)
        assert response.status_code in (200, 400), suffix
        assert_no_pii(response)


def test_to_field_parameter_cannot_address_pii_columns(staff_client, order):
    for path in (f"/admin/orders/order/{order.pk}/change/", "/admin/orders/order/"):
        response = staff_client.get(path, {"_to_field": "customer_phone"})
        assert response.status_code == 400
        assert_no_pii(response)


def test_history_page_has_no_pii(staff_client, order):
    response = staff_client.get(f"/admin/orders/order/{order.pk}/history/")
    assert response.status_code == 200
    assert_no_pii(response)


def test_unknown_and_malformed_ids_do_not_leak(staff_client, order):
    for object_id in ("999999", "abc"):
        response = staff_client.get(f"/admin/orders/order/{object_id}/change/", follow=True)
        assert response.status_code == 200
        assert_no_pii(response)


def test_forbidden_responses_carry_no_pii(make_staff, order):
    client = client_for(make_staff())
    for path in ("/admin/orders/order/", f"/admin/orders/order/{order.pk}/change/"):
        assert_no_pii(client.get(path))


# --- PII: search ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("term", [FULL_PHONE, "09123456789", "3456789", RECIPIENT, "Zhaleh", PROVINCE, CITY, "Quince", POSTAL])
def test_search_cannot_find_orders_by_pii_without_permission(staff_client, order, term):
    response = staff_client.get("/admin/orders/order/", {"q": term})
    assert response.status_code == 200
    assert response.context["cl"].result_count == 0
    assert_no_pii(response, echoed_query=term)


@pytest.mark.parametrize("term", ["3456789", "09123456789", FULL_PHONE, "Zhaleh"])
def test_search_by_phone_or_recipient_works_with_pii_permission(pii_client, order, make_variant_size, term):
    other = make_order(make_variant_size, phone="+989120000000", recipient_name="Someone Else")
    response = pii_client.get("/admin/orders/order/", {"q": term})
    ids = [o.pk for o in response.context["cl"].result_list]
    assert ids == [order.pk] and other.pk not in ids


def test_search_by_sku_product_and_order_id_works_without_pii_permission(staff_client, order, make_variant_size):
    other = make_order(make_variant_size, phone="+989120000000")
    item = order.items.get()
    for term in (item.sku, item.product_name):
        ids = [o.pk for o in staff_client.get("/admin/orders/order/", {"q": term}).context["cl"].result_list]
        assert order.pk in ids and other.pk not in ids
    by_id = staff_client.get("/admin/orders/order/", {"q": str(order.pk)}).context["cl"].result_list
    assert order.pk in [o.pk for o in by_id]  # other orders may also match on digits inside their SKU text


@pytest.mark.parametrize("term", ["abc", "9" * 40, "'; --", "%", "٣٤٥"])
def test_odd_search_terms_do_not_error(staff_client, pii_client, order, term):
    for client in (staff_client, pii_client):
        assert client.get("/admin/orders/order/", {"q": term}).status_code == 200


def test_item_search_never_matches_parent_pii(staff_client, order):
    for term in (FULL_PHONE, RECIPIENT, ADDRESS, "3456789"):
        response = staff_client.get("/admin/orders/orderitem/", {"q": term})
        assert response.status_code == 200 and response.context["cl"].result_count == 0
        assert_no_pii(response, echoed_query=term)


def test_search_fields_expose_pii_only_to_permission_holders(make_staff, superuser):
    ma = site_admin(Order)
    plain = ma.get_search_fields(request_for(make_staff(*VIEW)))
    assert not set(plain) & {"customer_phone", "recipient_name", "user__phone", "address", "postal_code"}
    assert "customer_phone" in ma.get_search_fields(request_for(make_staff(*VIEW, PII_PERMISSION)))
    assert "customer_phone" in ma.get_search_fields(request_for(superuser))


# --- PII: filters (query string), sorting ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "params",
    [
        {"customer_phone__startswith": "+9891"}, {"customer_phone": FULL_PHONE}, {"recipient_name__icontains": "Zhaleh"},
        {"province": PROVINCE}, {"city__startswith": "Abhar"}, {"address__contains": "Quince"},
        {"postal_code__startswith": "4567"}, {"user__phone__startswith": "+9891"}, {"items__sku__startswith": "SKU"},
    ],
)
def test_query_string_filters_on_pii_or_relations_are_rejected(staff_client, pii_client, su_client, order, params):
    for client in (staff_client, pii_client, su_client):
        response = client.get("/admin/orders/order/", params)
        assert response.status_code == 400
        assert_no_pii(response)


@pytest.mark.parametrize(
    "params",
    [
        {"order__customer_phone__startswith": "+9891"}, {"order__recipient_name": RECIPIENT},
        {"order__postal_code__startswith": "4567"}, {"order__user__phone__startswith": "+9891"},
        {"variant_size__sku__startswith": "SKU"},
    ],
)
def test_order_item_filters_across_relations_are_rejected(staff_client, su_client, order, params):
    for client in (staff_client, su_client):
        response = client.get("/admin/orders/orderitem/", params)
        assert response.status_code == 400
        assert_no_pii(response)


def test_safe_filters_still_work(staff_client, order):
    for params in ({"status": "pending"}, {"payment_status": "unpaid"}, {"id__exact": str(order.pk)}):
        response = staff_client.get("/admin/orders/order/", params)
        assert response.status_code == 200 and response.context["cl"].result_count == 1
        assert_no_pii(response)


def test_sidebar_filters_offer_no_pii_choices(staff_client, order):
    specs = staff_client.get("/admin/orders/order/").context["cl"].filter_specs
    assert {getattr(spec, "field_path", None) for spec in specs} <= {"status", "payment_status", "created_at"}


def test_phone_column_is_not_sortable_so_it_cannot_reveal_hidden_digits(staff_client, make_variant_size):
    first = make_order(make_variant_size, phone="+989120000111")
    second = make_order(make_variant_size, phone="+989120000999")
    ma = site_admin(Order)
    assert getattr(ma.masked_phone, "admin_order_field", None) is None
    assert not set(ma.list_display) & {"customer_phone", "recipient_name", "province", "city", "address", "postal_code"}
    index = list(ma.list_display).index("masked_phone")
    for sign in ("", "-"):
        response = staff_client.get("/admin/orders/order/", {"o": f"{sign}{index}"})
        assert [o.pk for o in response.context["cl"].result_list] == [second.pk, first.pk]  # default order only


def test_sorting_by_a_named_pii_field_is_ignored(staff_client, make_variant_size):
    first = make_order(make_variant_size, phone="+989120000111")
    second = make_order(make_variant_size, phone="+989120000999")
    for value in ("customer_phone", "-customer_phone", "province", "999"):
        response = staff_client.get("/admin/orders/order/", {"o": value})
        assert response.status_code in (200, 302)
        if response.status_code == 200:
            assert [o.pk for o in response.context["cl"].result_list] == [second.pk, first.pk]


# --- PII: order items, inline, related objects ----------------------------------------------------------------
def test_order_item_pages_show_item_data_without_parent_pii(staff_client, order):
    item = order.items.get()
    listing = staff_client.get("/admin/orders/orderitem/")
    detail = staff_client.get(f"/admin/orders/orderitem/{item.pk}/change/")
    for response in (listing, detail):
        assert response.status_code == 200
        assert item.sku in response.content.decode()
        assert_no_pii(response)


def test_order_item_pages_do_not_link_to_users_or_the_catalog(staff_client, order):
    item = order.items.get()
    for path in ("/admin/orders/orderitem/", f"/admin/orders/orderitem/{item.pk}/change/",
                 f"/admin/orders/order/{order.pk}/change/"):
        html = staff_client.get(path).content.decode()
        assert "/admin/accounts/" not in html and "/admin/catalog/" not in html


def test_inline_lists_items_for_staff_and_leaks_no_pii(staff_client, order):
    response = staff_client.get(f"/admin/orders/order/{order.pk}/change/")
    assert order.items.get().sku in response.content.decode()
    assert_no_pii(response)


def test_user_delete_confirmation_does_not_leak_order_pii(su_client, order):
    response = su_client.get(f"/admin/accounts/user/{order.user_id}/delete/")
    assert RECIPIENT not in response.content.decode() and ADDRESS not in response.content.decode()


def test_autocomplete_endpoint_cannot_be_used_to_read_pii(staff_client, order):
    response = staff_client.get(
        "/admin/autocomplete/", {"app_label": "orders", "model_name": "orderitem", "field_name": "order", "term": "0912"}
    )
    assert_no_pii(response)


# --- strictly read-only ---------------------------------------------------------------------------------------
def test_permission_hooks_deny_everything_for_every_kind_of_user(superuser, make_staff, order):
    item = order.items.get()
    users = (superuser, make_staff(*VIEW, PII_PERMISSION), make_staff(*VIEW),
             make_staff("orders.add_order", "orders.change_order", "orders.delete_order",
                        "orders.add_orderitem", "orders.change_orderitem", "orders.delete_orderitem"))
    for user in users:
        request = request_for(user)
        for ma, obj in ((site_admin(Order), order), (site_admin(OrderItem), item), (OrderItemInline(Order, django_admin.site), order)):
            assert ma.has_add_permission(request) is False
            assert ma.has_change_permission(request) is False and ma.has_change_permission(request, obj) is False
            assert ma.has_delete_permission(request) is False and ma.has_delete_permission(request, obj) is False


def test_admin_classes_expose_no_actions_and_no_inline_editing(superuser):
    request = request_for(superuser)
    for ma in (site_admin(Order), site_admin(OrderItem)):
        assert ma.actions is None and ma.get_actions(request) == {} and ma.list_editable == ()
    assert OrderItemInline.can_delete is False and OrderItemInline.extra == 0


@pytest.mark.parametrize("model_path", ["order", "orderitem"])
def test_add_is_denied_even_for_superuser(su_client, order, model_path):
    assert su_client.get(f"/admin/orders/{model_path}/add/").status_code == 403
    assert su_client.post(f"/admin/orders/{model_path}/add/", {"total": "5"}).status_code == 403
    assert Order.objects.count() == 1 and OrderItem.objects.count() == 1


def test_order_change_and_delete_are_denied_even_for_superuser(su_client, order):
    before = snapshot(order)
    url = f"/admin/orders/order/{order.pk}/change/"
    assert su_client.get(url).status_code == 200  # read-only view page
    assert su_client.post(url, {"status": "pending", "payment_status": "unpaid", "address": "Changed", "total": "1"}).status_code == 403
    assert su_client.get(f"/admin/orders/order/{order.pk}/delete/").status_code == 403
    assert su_client.post(f"/admin/orders/order/{order.pk}/delete/", {"post": "yes"}).status_code == 403
    assert snapshot(order) == before and Order.objects.filter(pk=order.pk).exists()


def test_order_item_change_and_delete_are_denied_even_for_superuser(su_client, order):
    item = order.items.get()
    before = snapshot(order)
    url = f"/admin/orders/orderitem/{item.pk}/change/"
    assert su_client.get(url).status_code == 200
    assert su_client.post(url, {"quantity": 99, "subtotal": "1"}).status_code == 403
    assert su_client.get(f"/admin/orders/orderitem/{item.pk}/delete/").status_code == 403
    assert su_client.post(f"/admin/orders/orderitem/{item.pk}/delete/", {"post": "yes"}).status_code == 403
    assert snapshot(order) == before and OrderItem.objects.filter(pk=item.pk).exists()


def test_view_only_staff_cannot_mutate_either(pii_client, order):
    before = snapshot(order)
    item = order.items.get()
    assert pii_client.post(f"/admin/orders/order/{order.pk}/change/", {"address": "Changed"}).status_code == 403
    assert pii_client.post(f"/admin/orders/orderitem/{item.pk}/change/", {"quantity": 9}).status_code == 403
    assert pii_client.post(f"/admin/orders/order/{order.pk}/delete/", {"post": "yes"}).status_code == 403
    assert snapshot(order) == before


def test_no_actions_on_the_changelist_and_posted_actions_do_nothing(su_client, order):
    for path in ("/admin/orders/order/", "/admin/orders/orderitem/"):
        response = su_client.get(path)
        assert response.context["action_form"] is None
        assert 'name="action"' not in response.content.decode()
    su_client.post("/admin/orders/order/", {"action": "delete_selected", "_selected_action": [order.pk], "post": "yes", "index": "0"})
    su_client.post("/admin/orders/orderitem/", {"action": "delete_selected", "_selected_action": [order.items.get().pk], "post": "yes", "index": "0"})
    assert Order.objects.filter(pk=order.pk).exists() and order.items.count() == 1


def test_inline_cannot_add_change_or_delete_rows(su_client, order):
    item = order.items.get()
    before = snapshot(order)
    response = su_client.post(
        f"/admin/orders/order/{order.pk}/change/",
        {
            "items-TOTAL_FORMS": "2", "items-INITIAL_FORMS": "1", "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "1000",
            "items-0-id": item.pk, "items-0-order": order.pk, "items-0-quantity": "50", "items-0-DELETE": "on",
            "items-1-order": order.pk, "items-1-sku": "INJECTED", "items-1-quantity": "1",
        },
    )
    assert response.status_code == 403
    assert snapshot(order) == before and not OrderItem.objects.filter(sku="INJECTED").exists()
    page = su_client.get(f"/admin/orders/order/{order.pk}/change/")
    for formset in page.context["inline_admin_formsets"]:
        assert not formset.has_add_permission and not formset.has_change_permission and not formset.has_delete_permission


def test_save_and_delete_hooks_refuse_even_if_called_directly(superuser, order):
    from django.core.exceptions import PermissionDenied

    request = request_for(superuser)
    for ma in (site_admin(Order), site_admin(OrderItem)):
        with pytest.raises(PermissionDenied):
            ma.save_model(request, order, None, True)
        with pytest.raises(PermissionDenied):
            ma.delete_model(request, order)
        with pytest.raises(PermissionDenied):
            ma.delete_queryset(request, Order.objects.all())
    assert Order.objects.filter(pk=order.pk).exists()


def test_mask_phone_helper():
    assert mask_phone(FULL_PHONE) == MASKED_PHONE
    assert mask_phone("") == "****" and mask_phone("12345678") == "****"


# --- query count ----------------------------------------------------------------------------------------------
def count_queries(client, path):
    client.get(path)  # warm process-wide caches so only steady-state queries are compared
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(path)
    assert response.status_code == 200
    return len(ctx)


@pytest.mark.parametrize("path", ["/admin/orders/order/", "/admin/orders/orderitem/"])
def test_changelist_query_count_does_not_grow_with_rows(make_staff, make_variant_size, path):
    client = client_for(make_staff(*VIEW, PII_PERMISSION))
    make_order(make_variant_size, items=1)
    make_order(make_variant_size, items=1)
    small = count_queries(client, path)
    for _ in range(8):
        make_order(make_variant_size, items=3)
    large = count_queries(client, path)
    assert large == small and large <= 20


def test_order_detail_query_count_does_not_grow_with_items(make_staff, make_variant_size):
    client = client_for(make_staff(*VIEW))
    one = make_order(make_variant_size, items=1)
    many = make_order(make_variant_size, items=12)
    assert count_queries(client, f"/admin/orders/order/{many.pk}/change/") == count_queries(
        client, f"/admin/orders/order/{one.pk}/change/"
    )


def test_changelist_search_query_count_is_bounded(make_staff, make_variant_size):
    client = client_for(make_staff(*VIEW, PII_PERMISSION))
    for _ in range(6):
        make_order(make_variant_size, items=2)
    assert count_queries(client, "/admin/orders/order/?q=Zhaleh") <= 20
    assert count_queries(client, "/admin/orders/order/?q=SKU") <= 20


def test_item_count_column_is_correct_with_search_joins(staff_client, make_variant_size):
    order = make_order(make_variant_size, items=3)
    result = staff_client.get("/admin/orders/order/", {"q": order.items.first().sku}).context["cl"].result_list
    assert [(o.pk, o._item_count) for o in result] == [(order.pk, 3)]


def test_admin_classes_registered():
    assert isinstance(site_admin(Order), OrderAdmin) and isinstance(site_admin(OrderItem), OrderItemAdmin)
