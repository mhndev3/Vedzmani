import json
import threading
from decimal import Decimal

import pytest
from django.db import connection
from django.test import Client

from apps.accounts.models import User
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, ColorVariant, Product, Size, VariantImage, VariantSize

CART = "/api/cart/"
ITEMS = "/api/cart/items/"


def make_vs(slug="hoodie", price="1000", sale=None, stock=5, active=True, sku=None, size_code="m"):
    cat = Category.objects.get_or_create(slug="tops", defaults={"name": "Tops"})[0]
    product, _ = Product.objects.get_or_create(
        slug=slug,
        defaults={"category": cat, "name": slug.title(), "price": Decimal(price),
                  "sale_price": Decimal(sale) if sale else None, "is_active": active},
    )
    variant = ColorVariant.objects.get_or_create(product=product, slug="black", defaults={"name": "Black"})[0]
    size = Size.objects.get_or_create(code=size_code, defaults={"label": size_code.upper()})[0]
    return VariantSize.objects.create(variant=variant, size=size, sku=sku or f"{slug}-{size_code}", stock_quantity=stock)


class Http:
    """Browser-like client: sessions + CSRF enforced (same as production)."""

    def __init__(self, api):
        self.api = api
        self.c = api.client

    def _h(self):
        return {"HTTP_X_CSRFTOKEN": self.api._token()}

    def get(self, path):
        return self.c.get(path)

    def send(self, method, path, data=None):
        return getattr(self.c, method)(path, data=json.dumps(data or {}), content_type="application/json", **self._h())


@pytest.fixture
def http(api):
    api.login("09120000001")
    return Http(api)


@pytest.fixture
def other():
    from tests.conftest import ApiClient

    a = ApiClient()
    a.login("09120000002")
    return Http(a)


pytestmark = pytest.mark.django_db


# --- authentication / CSRF ---------------------------------------------------------------------

def test_anonymous_gets_401_everywhere(api):
    vs = make_vs()
    assert api.get(CART).status_code == 401
    assert api.post(ITEMS, {"variant_size_id": vs.id, "quantity": 1}).status_code == 401
    h = Http(api)
    assert h.send("patch", ITEMS + "1/", {"quantity": 1}).status_code == 401
    assert h.send("delete", ITEMS + "1/").status_code == 401
    assert h.send("delete", CART).status_code == 401
    assert Cart.objects.count() == 0


def test_unsafe_methods_require_csrf(http):
    vs = make_vs()
    r = http.c.post(ITEMS, data=json.dumps({"variant_size_id": vs.id}), content_type="application/json")
    assert r.status_code == 403
    assert CartItem.objects.count() == 0


# --- read --------------------------------------------------------------------------------------

def test_empty_cart_does_not_create_rows(http):
    r = http.get(CART)
    assert r.status_code == 200
    assert r.json() == {"items": [], "item_count": 0, "total_quantity": 0, "total": "0", "has_issues": False}
    assert Cart.objects.count() == 0
    assert "no-store" in r["Cache-Control"] or "private" in r["Cache-Control"]


def test_add_returns_full_renderable_cart(http):
    vs = make_vs(price="1500", sale="1200")
    VariantImage.objects.create(variant=vs.variant, storage_key="a/b.webp", position=0, is_primary=True, width=10, height=20, alt_text="x")
    r = http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 2})
    assert r.status_code == 201
    body = r.json()
    (line,) = body["items"]
    assert line["quantity"] == 2 and line["availability"] == "available"
    assert line["unit_price"] == "1200" and line["subtotal"] == "2400"  # sale price wins, server-side
    assert line["product"]["slug"] == "hoodie" and line["color"]["slug"] == "black"
    assert line["variant_size"] == {"id": vs.id, "sku": "hoodie-m", "size": "m", "label": "M"}
    assert line["image"]["url"].endswith("a/b.webp") and line["image"]["width"] == 10
    assert body["total"] == "2400" and body["total_quantity"] == 2 and body["item_count"] == 1
    assert "stock_quantity" not in json.dumps(body)


def test_totals_use_decimal_over_multiple_lines(http):
    a, b = make_vs("a", "999"), make_vs("b", "12345", sale="10001")
    http.send("post", ITEMS, {"variant_size_id": a.id, "quantity": 3})
    r = http.send("post", ITEMS, {"variant_size_id": b.id, "quantity": 2})
    assert r.json()["total"] == str(Decimal("999") * 3 + Decimal("10001") * 2) == "22999"


def test_client_supplied_price_is_ignored(http):
    vs = make_vs(price="1000")
    r = http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 1, "unit_price": "1", "total": "1"})
    assert r.json()["total"] == "1000"


def test_price_changes_are_reflected_without_stale_copies(http):
    vs = make_vs(price="1000")
    http.send("post", ITEMS, {"variant_size_id": vs.id})
    Product.objects.update(price=Decimal("2000"))
    assert http.get(CART).json()["total"] == "2000"


# --- add ---------------------------------------------------------------------------------------

def test_add_same_variant_increments_one_line(http):
    vs = make_vs(stock=9)
    http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 2})
    r = http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 3})
    assert r.status_code == 201 and r.json()["items"][0]["quantity"] == 5
    assert CartItem.objects.count() == 1


def test_quantity_defaults_to_one(http):
    vs = make_vs()
    assert http.send("post", ITEMS, {"variant_size_id": vs.id}).json()["items"][0]["quantity"] == 1


@pytest.mark.parametrize("qty", [0, -1, 11, 1.5, "abc", None, [], True])
def test_add_rejects_bad_quantities(http, qty):
    vs = make_vs(stock=50)
    r = http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": qty})
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"
    assert CartItem.objects.count() == 0


@pytest.mark.parametrize("vid", [0, -3, "x", None, 1.5, 2**70, ""])
def test_add_rejects_malformed_identifiers(http, vid):
    r = http.send("post", ITEMS, {"variant_size_id": vid, "quantity": 1})
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"


def test_missing_identifier_and_non_object_body(http):
    assert http.send("post", ITEMS, {"quantity": 1}).status_code == 400
    r = http.c.post(ITEMS, data="[1]", content_type="application/json", **http._h())
    assert r.status_code == 400


def test_add_unknown_inactive_and_unpublished_look_identical(http):
    unpublished = make_vs("draft", active=False)
    inactive_size = make_vs("p2", sku="p2-x")
    VariantSize.objects.filter(pk=inactive_size.pk).update(is_active=False)
    inactive_variant = make_vs("p3", sku="p3-x")
    ColorVariant.objects.filter(pk=inactive_variant.variant_id).update(is_active=False)
    inactive_cat = make_vs("p4", sku="p4-x")
    Category.objects.filter(pk=inactive_cat.variant.product.category_id).update(is_active=False)
    responses = [http.send("post", ITEMS, {"variant_size_id": i}).json() for i in
                 (unpublished.id, inactive_size.id, inactive_variant.id, 10**9)]
    assert all(r == responses[0] and r["error"]["code"] == "validation_error" for r in responses)
    assert CartItem.objects.count() == 0


def test_add_beyond_stock_is_409_and_cart_unchanged(http):
    vs = make_vs(stock=2)
    assert http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 3}).json()["error"]["code"] == "insufficient_stock"
    out = make_vs("oos", stock=0)
    r = http.send("post", ITEMS, {"variant_size_id": out.id})
    assert r.status_code == 409 and r.json()["error"]["code"] == "insufficient_stock"
    assert CartItem.objects.count() == 0
    http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 2})
    assert http.send("post", ITEMS, {"variant_size_id": vs.id}).status_code == 409  # 2 + 1 > stock 2
    assert CartItem.objects.get().quantity == 2


def test_incremental_add_cannot_exceed_max_quantity(http):
    vs = make_vs(stock=100)
    http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 8})
    r = http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 3})
    assert r.status_code == 400 and r.json()["error"]["details"]["quantity"][0]["code"] == "max_quantity"
    assert CartItem.objects.get().quantity == 8


def test_line_limit(http, settings):
    settings.CART_MAX_LINES = 2
    ids = [make_vs(f"p{i}", sku=f"s{i}").id for i in range(3)]
    assert http.send("post", ITEMS, {"variant_size_id": ids[0]}).status_code == 201
    assert http.send("post", ITEMS, {"variant_size_id": ids[1]}).status_code == 201
    r = http.send("post", ITEMS, {"variant_size_id": ids[2]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "cart_full"
    assert http.send("post", ITEMS, {"variant_size_id": ids[0]}).status_code == 201  # existing line still editable


# --- update / remove / clear -------------------------------------------------------------------

def _line(http, vs, qty=1):
    return http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": qty}).json()["items"][-1]["id"]


def test_update_quantity(http):
    vs = make_vs(stock=5)
    item = _line(http, vs)
    r = http.send("patch", f"{ITEMS}{item}/", {"quantity": 4})
    assert r.status_code == 200 and r.json()["items"][0]["quantity"] == 4 and r.json()["total"] == "4000"
    assert http.send("patch", f"{ITEMS}{item}/", {"quantity": 1}).json()["items"][0]["quantity"] == 1


@pytest.mark.parametrize("qty", [0, -2, 11, "x", None, 2.5])
def test_update_rejects_bad_quantity(http, qty):
    vs = make_vs(stock=50)
    item = _line(http, vs)
    r = http.send("patch", f"{ITEMS}{item}/", {"quantity": qty})
    assert r.status_code == 400
    assert CartItem.objects.get().quantity == 1


def test_update_beyond_stock_is_409(http):
    vs = make_vs(stock=3)
    item = _line(http, vs)
    r = http.send("patch", f"{ITEMS}{item}/", {"quantity": 4})
    assert r.status_code == 409 and r.json()["error"]["code"] == "insufficient_stock"
    assert CartItem.objects.get().quantity == 1


def test_remove_item_and_not_found(http):
    a, b = make_vs("a"), make_vs("b")
    ia, _ib = _line(http, a), _line(http, b)
    r = http.send("delete", f"{ITEMS}{ia}/")
    assert r.status_code == 200 and [i["product"]["slug"] for i in r.json()["items"]] == ["b"]
    assert http.send("delete", f"{ITEMS}{ia}/").status_code == 404
    assert http.send("patch", f"{ITEMS}{ia}/", {"quantity": 1}).status_code == 404
    assert http.send("delete", f"{ITEMS}{2**70}/").status_code == 404
    assert http.send("delete", f"{ITEMS}abc/").status_code == 404


def test_clear_cart_and_clear_without_cart(http):
    assert http.send("delete", CART).json()["items"] == []  # no cart yet: idempotent, creates nothing
    assert Cart.objects.count() == 0
    _line(http, make_vs("a"))
    _line(http, make_vs("b"))
    r = http.send("delete", CART)
    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == "0"
    assert CartItem.objects.count() == 0


# --- ownership ---------------------------------------------------------------------------------

def test_users_cannot_see_or_modify_each_others_carts(http, other):
    vs = make_vs(stock=9)
    mine = _line(http, vs, 2)
    assert other.get(CART).json()["items"] == []
    assert other.send("patch", f"{ITEMS}{mine}/", {"quantity": 5}).status_code == 404
    assert other.send("delete", f"{ITEMS}{mine}/").status_code == 404
    other.send("delete", CART)  # clears only their own (empty) cart
    item = CartItem.objects.get()
    assert item.quantity == 2 and item.cart.user.phone == "+989120000001"
    # same variant in two carts stays independent
    other.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 7})
    assert CartItem.objects.count() == 2 and http.get(CART).json()["items"][0]["quantity"] == 2


def test_client_cannot_choose_the_owner(http, other):
    vs = make_vs()
    victim = User.objects.get(phone="+989120000002")
    http.send("post", ITEMS, {"variant_size_id": vs.id, "user": victim.id, "user_id": victim.id, "cart": 1})
    assert not CartItem.objects.filter(cart__user=victim).exists()
    assert CartItem.objects.filter(cart__user__phone="+989120000001").count() == 1


# --- availability changes after adding ---------------------------------------------------------

def test_unpublished_item_is_flagged_excluded_from_total_and_removable(http):
    a, b = make_vs("a", "100"), make_vs("b", "200")
    _line(http, a)
    ib = _line(http, b, 2)
    Product.objects.filter(slug="b").update(is_active=False)
    body = http.get(CART).json()
    by = {i["product"]["slug"]: i for i in body["items"]}
    assert by["b"]["availability"] == "unavailable" and by["a"]["availability"] == "available"
    assert body["total"] == "100" and body["total_quantity"] == 1 and body["has_issues"] is True
    r = http.send("patch", f"{ITEMS}{ib}/", {"quantity": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "item_unavailable"
    assert http.send("delete", f"{ITEMS}{ib}/").status_code == 200


def test_stock_drop_flags_insufficient_stock_but_allows_reducing(http):
    vs = make_vs(stock=5)
    item = _line(http, vs, 4)
    VariantSize.objects.filter(pk=vs.pk).update(stock_quantity=2)
    line = http.get(CART).json()["items"][0]
    assert line["availability"] == "insufficient_stock" and line["quantity"] == 4
    assert http.send("patch", f"{ITEMS}{item}/", {"quantity": 3}).status_code == 409
    assert http.send("patch", f"{ITEMS}{item}/", {"quantity": 2}).json()["items"][0]["availability"] == "available"


# --- stock is never touched --------------------------------------------------------------------

def test_cart_operations_never_change_stock(http):
    vs = make_vs(stock=5)
    item = _line(http, vs, 3)
    http.send("patch", f"{ITEMS}{item}/", {"quantity": 5})
    http.send("post", ITEMS, {"variant_size_id": vs.id, "quantity": 99})  # rejected
    http.get(CART)
    http.send("delete", f"{ITEMS}{item}/")
    _line(http, vs, 2)
    http.send("delete", CART)
    vs.refresh_from_db()
    assert vs.stock_quantity == 5


# --- performance -------------------------------------------------------------------------------

def test_read_query_count_is_constant(http, django_assert_max_num_queries):
    for i in range(6):
        vs = make_vs(f"p{i}", sku=f"s{i}")
        VariantImage.objects.create(variant=vs.variant, storage_key=f"p{i}.webp", width=1, height=1)
        _line(http, vs)
    with django_assert_max_num_queries(6):  # session + user + cart + items + images (+1 slack)
        assert len(http.get(CART).json()["items"]) == 6


# --- concurrency (real threads, real PostgreSQL connections) -----------------------------------

@pytest.mark.django_db(transaction=True)
def test_concurrent_adds_cannot_exceed_limits():
    user = User.objects.create_user("09125550000")
    vs = make_vs(stock=100)
    results, barrier = [], threading.Barrier(6)

    def worker():
        try:
            c = Client()
            c.force_login(user)
            barrier.wait()
            r = c.post(ITEMS, data=json.dumps({"variant_size_id": vs.id, "quantity": 4}), content_type="application/json")
            results.append(r.status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [201, 201, 400, 400, 400, 400]  # 4 + 4 = 8 fits; 12 > max 10
    assert CartItem.objects.get().quantity == 8
    assert Cart.objects.count() == 1
    vs.refresh_from_db()
    assert vs.stock_quantity == 100
