"""Order reading API (Agent 9, Session 2): GET /api/orders/ and GET /api/orders/<id>/.

Orders are created with the real `services.create_order` (the Session 1 code path), then read back over HTTP with
a browser-like session client. Nothing about ownership or the queryset is mocked."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.phone import normalize_phone
from apps.cart.models import CartItem
from apps.catalog.models import VariantSize
from apps.orders import services
from apps.orders.models import Order, OrderItem
from tests.conftest import DELIVERY, ApiClient
from tests.test_cart_api import Http, make_vs
from tests.test_orders_api import fill_cart, stock

ORDERS = "/api/orders/"
PHONE = "09120000001"
OTHER_PHONE = "09120000002"

pytestmark = pytest.mark.django_db


@pytest.fixture
def http(api):
    api.login(PHONE)
    return Http(api)


@pytest.fixture
def user(http):
    return User.objects.get(phone=normalize_phone(PHONE))


@pytest.fixture
def other_user():
    client = ApiClient()
    client.login(OTHER_PHONE)
    return User.objects.get(phone=normalize_phone(OTHER_PHONE))


def place(owner, *lines):
    """Place a real order for `owner` from the given (variant_size, quantity) lines."""
    fill_cart(owner, *lines)
    return services.create_order(owner, DELIVERY)


def detail(order_id):
    return f"{ORDERS}{order_id}/"


def assert_no_store(response):
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]


# --- authentication ---------------------------------------------------------------------------

def test_anonymous_cannot_list_orders(api, other_user):
    # `api` is never logged in here (the logged-in fixtures `http`/`user` are not requested).
    place(other_user, (make_vs(), 1))
    response = api.get(ORDERS)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert "09120000002" not in response.content.decode()


def test_anonymous_cannot_retrieve_an_order(api, other_user):
    order = place(other_user, (make_vs(), 1))
    response = api.get(detail(order.id))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_anonymous_gets_the_same_401_for_a_missing_order(api):
    assert api.get(detail(999999)).status_code == 401


# --- ownership --------------------------------------------------------------------------------

def test_list_contains_only_the_callers_orders(http, user, other_user):
    vs = make_vs(stock=20)
    mine_1 = place(user, (vs, 1))
    theirs = place(other_user, (vs, 2))
    mine_2 = place(user, (vs, 3))

    response = http.get(ORDERS)

    assert response.status_code == 200
    ids = [o["id"] for o in response.json()]
    assert set(ids) == {mine_1.id, mine_2.id}
    assert theirs.id not in ids
    assert "09120000002" not in response.content.decode()


def test_list_is_empty_for_a_user_without_orders(http, other_user):
    place(other_user, (make_vs(), 1))
    response = http.get(ORDERS)
    assert response.status_code == 200
    assert response.json() == []


def test_user_id_from_the_request_is_never_trusted(http, user, other_user):
    vs = make_vs(stock=20)
    mine = place(user, (vs, 1))
    theirs = place(other_user, (vs, 1))

    for query in (f"?user={other_user.id}", f"?user_id={other_user.id}", f"?owner={other_user.id}"):
        body = http.get(ORDERS + query).json()
        assert [o["id"] for o in body] == [mine.id], query
    assert http.get(detail(theirs.id) + f"?user={other_user.id}").status_code == 404


def test_user_can_retrieve_their_own_order(http, user):
    order = place(user, (make_vs(), 2))
    response = http.get(detail(order.id))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == order.id
    assert body["status"] == "pending"
    assert body["customer_phone"] == user.phone
    assert body["total"] == "2000"
    assert len(body["items"]) == 1


def test_another_users_order_is_404_not_403(http, other_user):
    theirs = place(other_user, (make_vs(), 1))
    response = http.get(detail(theirs.id))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "error"


def test_foreign_and_nonexistent_orders_are_indistinguishable(http, other_user):
    theirs = place(other_user, (make_vs(), 1))
    foreign = http.get(detail(theirs.id))
    missing = http.get(detail(theirs.id + 1000))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.content == missing.content
    assert "Cache-Control" in foreign and foreign["Cache-Control"] == missing["Cache-Control"]


# --- ordering ---------------------------------------------------------------------------------

def test_list_is_newest_first_with_id_as_tiebreaker(http, user):
    vs = make_vs(stock=20)
    oldest, newest, tie_low, tie_high = (place(user, (vs, 1)) for _ in range(4))
    now = timezone.now()
    Order.objects.filter(pk=oldest.pk).update(created_at=now - timedelta(days=3))
    Order.objects.filter(pk=newest.pk).update(created_at=now)
    Order.objects.filter(pk__in=[tie_low.pk, tie_high.pk]).update(created_at=now - timedelta(days=1))
    assert tie_low.id < tie_high.id

    ids = [o["id"] for o in http.get(ORDERS).json()]

    assert ids == [newest.id, tie_high.id, tie_low.id, oldest.id]
    assert ids == [o["id"] for o in http.get(ORDERS).json()]  # stable across requests


# --- response contents ------------------------------------------------------------------------

def test_items_quantities_prices_and_totals_are_returned_from_the_snapshot(http, user):
    hoodie = make_vs(slug="hoodie", price="1000", sale="800", stock=5, size_code="m")
    tee = make_vs(slug="tee", price="500", stock=3, size_code="l")
    order = place(user, (hoodie, 2), (tee, 1))

    body = http.get(detail(order.id)).json()

    # Delivery snapshot + payment_status were added by Agent 11 (additive); there is no shipping/fee key.
    assert set(body) == {
        "id", "status", "payment_status", "customer_phone", "recipient_name", "province", "city", "address",
        "postal_code", "total", "created_at", "items",
    }
    assert body["total"] == "2100"
    items = {i["sku"]: i for i in body["items"]}
    assert set(items["hoodie-m"]) == {
        "id", "variant_size_id", "product_name", "color_name", "size_label", "sku", "unit_price", "quantity",
        "subtotal",
    }
    assert items["hoodie-m"] == {
        "id": items["hoodie-m"]["id"], "variant_size_id": hoodie.id, "product_name": "Hoodie",
        "color_name": "Black", "size_label": "M", "sku": "hoodie-m", "unit_price": "800", "quantity": 2,
        "subtotal": "1600",
    }
    assert items["tee-l"]["unit_price"] == "500" and items["tee-l"]["subtotal"] == "500"
    assert sum(Decimal(i["subtotal"]) for i in body["items"]) == Decimal(body["total"])
    assert [i["id"] for i in body["items"]] == sorted(i["id"] for i in body["items"])  # stable item order


def test_list_and_detail_return_the_same_order_representation(http, user):
    order = place(user, (make_vs(), 2))
    assert http.get(ORDERS).json() == [http.get(detail(order.id)).json()]


def test_changing_the_live_catalog_does_not_rewrite_the_api_response(http, user):
    vs = make_vs(slug="hoodie", price="1000", stock=5)
    order = place(user, (vs, 2))
    list_before = http.get(ORDERS).json()
    detail_before = http.get(detail(order.id)).json()

    product = vs.variant.product
    product.name, product.price, product.sale_price = "Renamed", Decimal("1"), None
    product.save()
    vs.variant.name = "Red"
    vs.variant.save()
    vs.sku = "NEW-SKU"
    vs.save()
    vs.size.label = "Medium"
    vs.size.save()
    user.phone = normalize_phone("09129999999")
    user.save()

    assert http.get(ORDERS).json() == list_before
    assert http.get(detail(order.id)).json() == detail_before
    item = detail_before["items"][0]
    assert (item["product_name"], item["color_name"], item["size_label"], item["sku"]) == (
        "Hoodie", "Black", "M", "hoodie-m",
    )
    assert item["unit_price"] == "1000" and detail_before["total"] == "2000"
    assert detail_before["customer_phone"] == normalize_phone(PHONE)


def test_order_survives_its_variant_being_deactivated(http, user):
    vs = make_vs(slug="hoodie", stock=5)
    order = place(user, (vs, 1))
    vs.variant.product.is_active = False
    vs.variant.product.save()
    response = http.get(detail(order.id))
    assert response.status_code == 200
    assert response.json()["items"][0]["product_name"] == "Hoodie"


# --- caching ----------------------------------------------------------------------------------

def test_every_order_read_response_is_no_store(http, api, user, other_user):
    order = place(user, (make_vs(), 1))
    theirs = place(other_user, (make_vs(slug="tee", size_code="l"), 1))

    for response in (http.get(ORDERS), http.get(detail(order.id)), http.get(detail(theirs.id)),
                     http.get(detail(order.id + 5000))):
        assert_no_store(response)

    anonymous = ApiClient()
    assert_no_store(anonymous.get(ORDERS))
    assert_no_store(anonymous.get(detail(order.id)))


# --- reads are side-effect free ---------------------------------------------------------------

def test_get_requests_do_not_mutate_anything(http, user):
    vs = make_vs(stock=10)
    other_vs = make_vs(slug="tee", size_code="l", stock=4)
    order = place(user, (vs, 2))
    fill_cart(user, (other_vs, 1))  # a live cart that must stay untouched
    order_before = Order.objects.filter(pk=order.pk).values().get()
    items_before = list(OrderItem.objects.values())
    cart_before = list(CartItem.objects.values())
    stock_before = (stock(vs), stock(other_vs))

    for _ in range(2):
        assert http.get(ORDERS).status_code == 200
        assert http.get(detail(order.id)).status_code == 200

    assert Order.objects.filter(pk=order.pk).values().get() == order_before  # incl. updated_at
    assert list(OrderItem.objects.values()) == items_before
    assert list(CartItem.objects.values()) == cart_before
    assert (stock(vs), stock(other_vs)) == stock_before == (8, 4)
    assert Order.objects.count() == 1


def test_query_count_does_not_grow_with_the_number_of_orders(http, user):
    vs = make_vs(stock=50)
    place(user, (vs, 1))
    http.get(ORDERS)  # warm session/csrf paths
    with CaptureQueriesContext(connection) as one:
        http.get(ORDERS)
    tee = make_vs(slug="tee", size_code="l", stock=50)
    for _ in range(4):
        place(user, (vs, 1), (tee, 1))
    with CaptureQueriesContext(connection) as many:
        assert len(http.get(ORDERS).json()) == 5
    assert len(many) == len(one)


# --- unsupported methods ----------------------------------------------------------------------

@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_unsupported_methods_on_the_list_return_405(http, user, method):
    order = place(user, (make_vs(), 1))
    before = Order.objects.filter(pk=order.pk).values().get()
    response = http.send(method, ORDERS)
    assert response.status_code == 405
    assert Order.objects.filter(pk=order.pk).values().get() == before


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_unsupported_methods_on_the_detail_return_405(http, user, method):
    vs = make_vs(stock=10)
    order = place(user, (vs, 1))
    fill_cart(user, (vs, 1))  # a POST here must not create an order from this cart
    before = Order.objects.filter(pk=order.pk).values().get()

    response = http.send(method, detail(order.id))

    assert response.status_code == 405
    assert Order.objects.count() == 1
    assert Order.objects.filter(pk=order.pk).values().get() == before
    assert CartItem.objects.count() == 1 and stock(vs) == 9


def test_deleting_a_foreign_order_is_405_and_leaves_it_intact(http, other_user):
    theirs = place(other_user, (make_vs(), 1))
    assert http.send("delete", detail(theirs.id)).status_code == 405
    assert Order.objects.filter(pk=theirs.pk).exists()


def test_non_numeric_order_id_is_not_routed(http):
    assert http.get(f"{ORDERS}abc/").status_code == 404
