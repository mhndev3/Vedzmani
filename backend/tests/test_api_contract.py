"""Cross-cutting API contract tests (Agent F).

These pin what a frontend can rely on across endpoints; per-endpoint behavior is
tested in the per-domain test modules and documented in backend/API.md.
Assertions are deliberately tolerant of ADDITIVE changes (extra response keys),
so a later agent adding fields does not break them.
"""

import json

import pytest
from django.test import Client

PUBLIC_GET = [
    "/api/health/",
    "/api/health/ready/",
    "/api/auth/csrf/",
    "/api/catalog/filters/",
    "/api/catalog/products/",
]

# (method, path, body) - every one of these requires a logged-in session.
SESSION_ONLY = [
    ("get", "/api/auth/me/", None),
    ("get", "/api/cart/", None),
    ("delete", "/api/cart/", None),
    ("post", "/api/cart/items/", {"variant_size_id": 1}),
    ("patch", "/api/cart/items/1/", {"quantity": 1}),
    ("delete", "/api/cart/items/1/", None),
    ("get", "/api/orders/", None),
    ("get", "/api/orders/1/", None),
    ("post", "/api/orders/", None),
]


def call(client, method, path, body=None):
    kwargs = {}
    if body is not None:
        kwargs = {"data": json.dumps(body), "content_type": "application/json"}
    return getattr(client, method)(path, **kwargs)


def assert_error_envelope(response, status, code=None):
    assert response.status_code == status, response.content
    body = response.json()
    assert set(body) == {"error"}, body
    error = body["error"]
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert set(error) <= {"code", "message", "details"}, error
    if code is not None:
        assert error["code"] == code, error
    return error


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_GET)
def test_public_endpoints_need_no_session(path):
    response = Client().get(path)
    assert response.status_code == 200, response.content
    assert response["Content-Type"].startswith("application/json")


@pytest.mark.django_db
@pytest.mark.parametrize(("method", "path", "body"), SESSION_ONLY)
def test_session_endpoints_answer_401_envelope_when_anonymous(method, path, body):
    response = call(Client(), method, path, body)
    assert_error_envelope(response, 401, "not_authenticated")
    assert response["WWW-Authenticate"] == "Session"


@pytest.mark.django_db
def test_csrf_endpoint_returns_token_and_sets_cookie():
    client = Client()
    response = client.get("/api/auth/csrf/")
    body = response.json()
    assert isinstance(body["csrfToken"], str) and body["csrfToken"]
    assert "csrftoken" in client.cookies


@pytest.mark.django_db
def test_unsafe_request_without_csrf_token_gets_403_envelope(api, make_variant_size):
    api.login()
    vs = make_variant_size()
    response = api.post("/api/cart/items/", {"variant_size_id": vs.id}, csrf=False)
    assert_error_envelope(response, 403, "csrf_failed")


@pytest.mark.django_db
def test_validation_error_envelope_has_field_details(api):
    response = api.get("/api/catalog/products/?sort=bogus")
    error = assert_error_envelope(response, 400, "validation_error")
    assert isinstance(error["details"], dict) and error["details"]
    (field_errors,) = list(error["details"].values())[:1]
    assert field_errors[0]["code"] and field_errors[0]["message"]


@pytest.mark.django_db
def test_not_found_uses_the_error_envelope(api):
    # The 'code' value differs between 404 sources today (see API.md, "Known
    # inconsistencies"), so only the envelope shape is pinned here.
    assert_error_envelope(api.get("/api/catalog/products/no-such-product/"), 404)
    assert_error_envelope(api.get("/api/catalog/products/?page=999"), 404)


@pytest.mark.django_db
def test_wrong_method_is_405(api):
    assert Client().post("/api/health/").status_code == 405
    assert api.post("/api/catalog/products/", {}).status_code == 405


@pytest.mark.django_db
def test_catalog_listing_is_paginated_with_documented_keys_and_string_money(api, make_variant_size):
    make_variant_size()
    body = api.get("/api/catalog/products/").json()
    assert {"count", "next", "previous", "results"} <= set(body)
    card = body["results"][0]
    assert {"id", "name", "slug", "price", "sale_price", "category", "in_stock", "image", "colors"} <= set(card)
    assert isinstance(card["price"], str)  # money is a Decimal rendered as a string, never a JSON number


@pytest.mark.django_db
def test_private_responses_are_not_cacheable(api):
    api.login()
    for path in ("/api/cart/", "/api/orders/"):
        cache_control = api.get(path)["Cache-Control"]
        assert "no-store" in cache_control, (path, cache_control)


@pytest.mark.django_db
def test_detail_to_cart_to_order_handoff_uses_variant_size_id(api, make_variant_size):
    """The one cross-endpoint chain a storefront needs: product detail ->
    cart add -> order create, keyed by colors[].sizes[].id (= VariantSize.id)."""
    vs = make_variant_size(stock=3)
    detail = api.get(f"/api/catalog/products/{vs.variant.product.slug}/").json()
    size_id = detail["colors"][0]["sizes"][0]["id"]
    assert size_id == vs.id

    api.login()
    added = api.post("/api/cart/items/", {"variant_size_id": size_id, "quantity": 2})
    assert added.status_code == 201, added.content
    cart = added.json()
    assert {"items", "item_count", "total_quantity", "total", "has_issues"} <= set(cart)
    assert cart["items"][0]["variant_size"]["id"] == size_id
    assert cart["items"][0]["quantity"] == 2

    created = api.post("/api/orders/")
    assert created.status_code == 201, created.content
    order = created.json()
    assert {"id", "status", "customer_phone", "total", "created_at", "items"} <= set(order)
    assert order["items"][0]["variant_size_id"] == size_id

    assert api.get("/api/cart/").json()["items"] == []  # cart cleared by order creation
    assert api.get(f"/api/orders/{order['id']}/").json()["id"] == order["id"]
    assert [o["id"] for o in api.get("/api/orders/").json()] == [order["id"]]  # plain array, not paginated


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    ["/api/nope/", "/api/cart/items/abc/", "/api/orders/abc/", "/api/catalog/nope/"],
)
def test_unknown_api_routes_answer_json_404_envelope(path):
    error = assert_error_envelope(Client().get(path), 404, "not_found")
    assert "details" not in error


@pytest.mark.django_db
def test_non_api_404_is_not_json():
    response = Client().get("/definitely-not-a-route/")
    assert response.status_code == 404
    assert not response["Content-Type"].startswith("application/json")


@pytest.mark.django_db
def test_me_is_not_cacheable(api):
    api.login()
    response = api.get("/api/auth/me/")
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"] or "private" in response["Cache-Control"]
    assert "no-cache" in response["Cache-Control"] or "no-store" in response["Cache-Control"]


@pytest.mark.django_db
@pytest.mark.parametrize(("method", "path"), [("post", "/api/orders/"), ("post", "/api/auth/logout/")])
def test_csrf_failure_code_is_the_same_everywhere(api, method, path):
    api.login()
    response = getattr(api, method)(path, {}, csrf=False)
    error = assert_error_envelope(response, 403, "csrf_failed")
    assert "CSRF Failed" not in error["message"]  # the reason is not echoed
