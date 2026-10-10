import json
import threading
from decimal import Decimal

import pytest
from django.db import connection
from django.db.models import ProtectedError
from django.test import Client

from apps.accounts.models import User
from apps.accounts.phone import normalize_phone
from apps.cart.models import Cart, CartItem
from apps.catalog.models import VariantSize
from apps.orders import services
from apps.orders.models import Order, OrderItem
from tests.test_cart_api import Http, make_vs

ORDERS = "/api/orders/"
PHONE = "09120000001"

pytestmark = pytest.mark.django_db


@pytest.fixture
def http(api):
    api.login(PHONE)
    return Http(api)


@pytest.fixture
def other():
    from tests.conftest import ApiClient

    client = ApiClient()
    client.login("09120000002")
    return Http(client)


@pytest.fixture
def user(http):
    return User.objects.get(phone=normalize_phone(PHONE))


def fill_cart(owner, *lines):
    cart, _ = Cart.objects.get_or_create(user=owner)
    for vs, quantity in lines:
        CartItem.objects.create(cart=cart, variant_size=vs, quantity=quantity)
    return cart


def stock(vs):
    return VariantSize.objects.get(pk=vs.pk).stock_quantity


def error_code(response):
    return response.json()["error"]["code"]


def assert_nothing_changed(owner, stocks):
    assert Order.objects.count() == 0 and OrderItem.objects.count() == 0
    assert CartItem.objects.filter(cart__user=owner).count() == len(stocks)
    for vs, expected in stocks:
        assert stock(vs) == expected


# --- authentication / CSRF -------------------------------------------------------------------

def test_anonymous_gets_401_and_creates_nothing(api):
    vs = make_vs()
    assert api.post(ORDERS, {}).status_code == 401
    assert Order.objects.count() == 0 and stock(vs) == 5


def test_csrf_is_enforced(http, user):
    vs = make_vs()
    fill_cart(user, (vs, 1))
    response = http.api.post(ORDERS, {}, csrf=False)
    assert response.status_code == 403
    assert Order.objects.count() == 0 and stock(vs) == 5 and CartItem.objects.count() == 1


def test_only_post_is_allowed(http):
    assert http.get(ORDERS).status_code == 405


# --- success ---------------------------------------------------------------------------------

def test_creates_order_with_snapshot_total_stock_and_clears_cart(http, user):
    hoodie = make_vs(slug="hoodie", price="1000", sale="800", stock=5, size_code="m")
    tee = make_vs(slug="tee", price="500", stock=3, size_code="l")
    fill_cart(user, (hoodie, 2), (tee, 1))

    response = http.send("post", ORDERS)

    assert response.status_code == 201, response.content
    assert response["Cache-Control"].find("no-store") != -1
    body = response.json()
    order = Order.objects.get()
    assert body["id"] == order.id
    assert body["status"] == "pending" == order.status
    assert body["customer_phone"] == user.phone == order.customer_phone
    assert body["total"] == "2100" and order.total == Decimal("2100")  # 800*2 + 500, sale price applied
    assert order.user == user
    by_sku = {i["sku"]: i for i in body["items"]}
    assert by_sku["hoodie-m"] == {
        "id": by_sku["hoodie-m"]["id"], "variant_size_id": hoodie.id, "product_name": "Hoodie",
        "color_name": "Black", "size_label": "M", "sku": "hoodie-m", "unit_price": "800", "quantity": 2,
        "subtotal": "1600",
    }
    assert by_sku["tee-l"]["unit_price"] == "500" and by_sku["tee-l"]["subtotal"] == "500"
    assert (stock(hoodie), stock(tee)) == (3, 2)
    assert CartItem.objects.count() == 0  # cart emptied, cart row itself kept
    assert Cart.objects.filter(user=user).exists()


def test_can_buy_exactly_the_remaining_stock(http, user):
    vs = make_vs(stock=3)
    fill_cart(user, (vs, 3))
    assert http.send("post", ORDERS).status_code == 201
    assert stock(vs) == 0


def test_price_is_read_at_checkout_not_when_added_to_cart(http, user):
    vs = make_vs(price="1000", stock=5)
    fill_cart(user, (vs, 2))
    product = vs.variant.product
    product.sale_price = Decimal("700")
    product.save()
    body = http.send("post", ORDERS).json()
    assert body["total"] == "1400" and body["items"][0]["unit_price"] == "700"


def test_client_supplied_fields_are_ignored_and_other_carts_untouched(http, user, other):
    mine = make_vs(slug="mine", price="1000", stock=5)
    theirs = make_vs(slug="theirs", price="9", stock=5)
    other_user = User.objects.get(phone=normalize_phone("09120000002"))
    fill_cart(user, (mine, 1))
    fill_cart(other_user, (theirs, 4))

    response = http.send(
        "post", ORDERS,
        {"user": other_user.id, "user_id": other_user.id, "total": "1", "unit_price": "1", "status": "paid",
         "items": [{"variant_size_id": theirs.id, "quantity": 4, "unit_price": "1"}]},
    )

    assert response.status_code == 201
    order = Order.objects.get()
    assert order.user == user and order.total == Decimal("1000") and order.status == "pending"
    assert [i.sku for i in order.items.all()] == ["mine-m"]
    assert (stock(mine), stock(theirs)) == (4, 5)
    assert CartItem.objects.filter(cart__user=other_user).get().quantity == 4  # untouched


# --- invalid carts ---------------------------------------------------------------------------

def test_missing_cart_and_empty_cart_are_rejected(http, user):
    response = http.send("post", ORDERS)
    assert response.status_code == 400 and error_code(response) == "empty_cart"
    Cart.objects.create(user=user)
    response = http.send("post", ORDERS)
    assert response.status_code == 400 and error_code(response) == "empty_cart"
    assert Order.objects.count() == 0


def test_second_submission_does_not_create_another_order(http, user):
    vs = make_vs(stock=5)
    fill_cart(user, (vs, 2))
    assert http.send("post", ORDERS).status_code == 201
    response = http.send("post", ORDERS)
    assert response.status_code == 400 and error_code(response) == "empty_cart"
    assert Order.objects.count() == 1 and stock(vs) == 3


# --- stock / availability: whole order rejected, nothing changes -----------------------------

def test_insufficient_stock_rejects_whole_order(http, user):
    ok = make_vs(slug="ok", stock=5, size_code="m")
    short = make_vs(slug="short", stock=3, size_code="l")
    fill_cart(user, (ok, 2), (short, 3))
    short.stock_quantity = 2  # stock dropped after the item was added to the cart
    short.save()

    response = http.send("post", ORDERS)

    assert response.status_code == 409 and error_code(response) == "insufficient_stock"
    assert_nothing_changed(user, [(ok, 5), (short, 2)])
    assert sorted(CartItem.objects.values_list("quantity", flat=True)) == [2, 3]


def test_out_of_stock_item_is_rejected(http, user):
    vs = make_vs(stock=1)
    fill_cart(user, (vs, 1))
    vs.stock_quantity = 0
    vs.save()
    response = http.send("post", ORDERS)
    assert response.status_code == 409 and error_code(response) == "insufficient_stock"
    assert_nothing_changed(user, [(vs, 0)])


def _deactivate_product(vs):
    vs.variant.product.is_active = False
    vs.variant.product.save()


def _deactivate_category(vs):
    vs.variant.product.category.is_active = False
    vs.variant.product.category.save()


def _deactivate_variant(vs):
    vs.variant.is_active = False
    vs.variant.save()


def _deactivate_size(vs):
    vs.is_active = False
    vs.save()


@pytest.mark.parametrize("deactivate", [_deactivate_product, _deactivate_category, _deactivate_variant, _deactivate_size])
def test_unavailable_item_rejects_whole_order(http, user, deactivate):
    good = make_vs(slug="good", stock=5, size_code="m")
    gone = make_vs(slug="gone", stock=5, size_code="l")
    fill_cart(user, (good, 1), (gone, 1))
    deactivate(gone)

    response = http.send("post", ORDERS)

    assert response.status_code == 409 and error_code(response) == "item_unavailable"
    assert_nothing_changed(user, [(good, 5), (gone, 5)])


def test_unavailable_takes_precedence_over_insufficient_stock(http, user):
    gone = make_vs(slug="gone", stock=5, size_code="m")
    short = make_vs(slug="short", stock=5, size_code="l")
    fill_cart(user, (gone, 1), (short, 5))
    _deactivate_product(gone)
    short.stock_quantity = 1
    short.save()
    assert error_code(http.send("post", ORDERS)) == "item_unavailable"
    assert_nothing_changed(user, [(gone, 5), (short, 1)])


# --- snapshots are independent of the live catalog -------------------------------------------

def test_order_items_do_not_change_when_the_catalog_changes(http, user):
    vs = make_vs(slug="hoodie", price="1000", stock=5)
    fill_cart(user, (vs, 2))
    http.send("post", ORDERS)
    before = list(OrderItem.objects.values())

    product = vs.variant.product
    product.name, product.price, product.sale_price = "Renamed", Decimal("1"), None
    product.save()
    vs.variant.name = "Red"
    vs.variant.save()
    vs.sku = "NEW-SKU"
    vs.save()
    vs.size.label = "Medium"
    vs.size.save()

    assert list(OrderItem.objects.values()) == before
    assert Order.objects.get().total == Decimal("2000")


def test_ordered_variant_size_cannot_be_deleted(http, user):
    vs = make_vs(stock=5)
    fill_cart(user, (vs, 1))
    http.send("post", ORDERS)
    with pytest.raises(ProtectedError):
        vs.delete()


# --- atomicity: a failure at any point leaves no order, no stock change, cart intact ---------

def _fail_clearing_cart(monkeypatch):
    def boom(cart):
        raise RuntimeError("boom")

    monkeypatch.setattr(services, "_clear_cart", boom)


def _fail_creating_items(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(OrderItem.objects, "bulk_create", boom)  # after stock decrement + order insert


@pytest.mark.parametrize("fail", [_fail_clearing_cart, _fail_creating_items])
def test_failure_mid_transaction_rolls_everything_back(http, user, monkeypatch, fail):
    a = make_vs(slug="a", stock=5, size_code="m")
    b = make_vs(slug="b", stock=4, size_code="l")
    fill_cart(user, (a, 2), (b, 3))
    fail(monkeypatch)

    with pytest.raises(RuntimeError):
        http.send("post", ORDERS)

    assert_nothing_changed(user, [(a, 5), (b, 4)])
    assert sorted(CartItem.objects.values_list("quantity", flat=True)) == [2, 3]


# --- concurrency (real threads, real PostgreSQL connections) ---------------------------------

def _run_threads(target, count):
    results, barrier = [], threading.Barrier(count)

    def worker(index):
        try:
            client = Client()
            client.force_login(target(index))
            barrier.wait()
            response = client.post(ORDERS, data="{}", content_type="application/json")
            results.append(response.status_code)
        except Exception as exc:  # noqa: BLE001 - surfaced by the assertions below
            results.append(repr(exc))
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return sorted(results, key=str)


@pytest.mark.django_db(transaction=True)
def test_last_unit_cannot_be_oversold():
    vs = make_vs(stock=1)
    users = [User.objects.create_user(f"0913000000{i}") for i in range(2)]
    for u in users:
        fill_cart(u, (vs, 1))

    assert _run_threads(lambda i: users[i], 2) == [201, 409]

    assert stock(vs) == 0
    assert Order.objects.count() == 1 and OrderItem.objects.get().quantity == 1
    assert CartItem.objects.count() == 1  # the loser's cart is untouched


@pytest.mark.django_db(transaction=True)
def test_double_submit_by_one_user_creates_one_order():
    user = User.objects.create_user("09131111111")
    vs = make_vs(stock=10)
    fill_cart(user, (vs, 3))

    assert _run_threads(lambda i: user, 4) == [201, 400, 400, 400]

    assert Order.objects.count() == 1 and stock(vs) == 7 and CartItem.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_over_same_items_do_not_deadlock_or_miscount():
    a = make_vs(slug="a", stock=100, size_code="m")
    b = make_vs(slug="b", stock=100, size_code="l")
    users = [User.objects.create_user(f"0914000000{i}") for i in range(6)]
    for index, u in enumerate(users):  # opposite insertion order on purpose
        fill_cart(u, *(((a, 2), (b, 2)) if index % 2 else ((b, 2), (a, 2))))

    assert _run_threads(lambda i: users[i], 6) == [201] * 6

    assert (stock(a), stock(b)) == (88, 88)
    assert Order.objects.count() == 6 and OrderItem.objects.count() == 12
