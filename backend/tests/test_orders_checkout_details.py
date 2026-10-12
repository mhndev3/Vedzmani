"""Checkout delivery details (Agent 11, Session 1): POST /api/orders/ now takes Iranian delivery details.

Browser-like client (sessions + CSRF enforced) against real PostgreSQL, like the other order tests.
The delivery phone is NOT part of the contract: it is the authenticated account's phone (`customer_phone`).
No shipping cost exists: `total` is the sum of the line subtotals only.
"""

from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.cart.models import Cart, CartItem
from apps.catalog.models import VariantSize
from apps.accounts.phone import normalize_phone
from apps.orders import services
from apps.orders.models import Order
from apps.orders.serializers import CheckoutSerializer
from tests.conftest import DELIVERY, ApiClient
from tests.test_cart_api import Http, make_vs
from tests.test_orders_api import assert_nothing_changed, checkout, error_code, fill_cart, world

ORDERS = "/api/orders/"
PHONE = "09120000001"

pytestmark = pytest.mark.django_db


@pytest.fixture
def http(api):
    api.login(PHONE)
    return Http(api)


@pytest.fixture
def user(http):
    return User.objects.get(phone=normalize_phone(PHONE))


@pytest.fixture
def cart(user):
    """One purchasable line: 2 x 1000 = 2000, stock 5. Returns the VariantSize."""
    vs = make_vs(price="1000", stock=5)
    fill_cart(user, (vs, 2))
    return vs


@pytest.fixture
def before(user, cart):
    """Complete state right before the request under test (cart filled, nothing ordered yet)."""
    return world(user)


def field_errors(response, field):
    return response.json()["error"]["details"][field]


# --- contract shape ----------------------------------------------------------------------------

def test_checkout_input_is_exactly_the_delivery_fields():
    assert set(CheckoutSerializer().fields) == set(Order.DELIVERY_FIELDS)
    assert not {"phone", "recipient_phone", "total", "status", "payment_status", "user"} & set(Order.DELIVERY_FIELDS)


# --- success -----------------------------------------------------------------------------------

def test_valid_checkout_snapshots_delivery_details_and_stays_unpaid(http, user, cart):
    response = checkout(http, recipient_name="  علی رضایی  ", postal_code="۱۲۳۴۵۶۷۸۹۰")

    assert response.status_code == 201, response.content
    body, order = response.json(), Order.objects.get()
    expected = {
        "recipient_name": "علی رضایی",  # trimmed, Persian text preserved
        "province": "Tehran",
        "city": "Tehran",
        "address": "No. 1, Example St.",
        "postal_code": "1234567890",  # Persian digits normalized to ASCII
    }
    for field, value in expected.items():
        assert body[field] == value == getattr(order, field)
    assert body["payment_status"] == "unpaid" == order.payment_status
    assert body["status"] == "pending"
    assert body["customer_phone"] == user.phone == order.customer_phone
    assert body["total"] == "2000"  # lines only
    assert not any("ship" in key or "fee" in key for key in body)  # no shipping cost is invented
    assert stock_after(cart) == 3


def stock_after(vs):
    return VariantSize.objects.get(pk=vs.pk).stock_quantity


def test_maximum_lengths_are_accepted(http, cart):
    response = checkout(http, recipient_name="ن" * 120, province="ت" * 60, city="ش" * 60, address="خ" * 255)
    assert response.status_code == 201, response.content


def test_zero_width_non_joiner_is_allowed_in_persian_text(http, cart):
    assert checkout(http, recipient_name="می‌خواهم").status_code == 201


def test_list_and_detail_return_the_same_delivery_snapshot(http, cart):
    created = checkout(http).json()
    assert http.get(ORDERS).json() == [created]
    assert http.get(f"{ORDERS}{created['id']}/").json() == created


def test_order_without_delivery_details_is_still_readable(http, user):
    """Orders created before delivery details existed have blank columns and `unpaid`."""
    legacy = Order.objects.create(user=user, customer_phone=user.phone, total=Decimal("100"))
    body = http.get(f"{ORDERS}{legacy.id}/").json()
    assert [body[f] for f in Order.DELIVERY_FIELDS] == ["", "", "", "", ""]
    assert body["payment_status"] == "unpaid"
    assert http.get(ORDERS).status_code == 200


# --- validation: nothing is created, stock and cart are untouched -------------------------------

@pytest.mark.parametrize("field", Order.DELIVERY_FIELDS)
def test_missing_field_is_rejected_and_changes_nothing(http, user, cart, field, before):
    response = http.send("post", ORDERS, {k: v for k, v in DELIVERY.items() if k != field})
    assert response.status_code == 400 and error_code(response) == "validation_error"
    assert field_errors(response, field)[0]["code"] == "required"
    assert_nothing_changed(user, before)


@pytest.mark.parametrize("field", Order.DELIVERY_FIELDS)
@pytest.mark.parametrize("value", ["", "   ", "\n", "\t"])
def test_blank_field_is_rejected_and_changes_nothing(http, user, cart, field, value, before):
    response = checkout(http, **{field: value})
    assert response.status_code == 400 and error_code(response) == "validation_error"
    assert field_errors(response, field)[0]["code"] == "blank"
    assert_nothing_changed(user, before)


@pytest.mark.parametrize("field", Order.DELIVERY_FIELDS)
def test_null_field_is_rejected(http, user, cart, field, before):
    response = checkout(http, **{field: None})
    assert response.status_code == 400 and field_errors(response, field)[0]["code"] == "null"
    assert_nothing_changed(user, before)


@pytest.mark.parametrize(
    "field, length", [("recipient_name", 121), ("province", 61), ("city", 61), ("address", 256)]
)
def test_over_length_field_is_rejected_and_changes_nothing(http, user, cart, field, length, before):
    response = checkout(http, **{field: "x" * length})
    assert response.status_code == 400 and field_errors(response, field)[0]["code"] == "max_length"
    assert_nothing_changed(user, before)


@pytest.mark.parametrize(
    "postal_code",
    ["123456789", "12345678901", "12345-67890", "1234 567890", "12345abcde", "１２３４５６７８９０", "abc"],
)
def test_invalid_postal_code_is_rejected_and_changes_nothing(http, user, cart, postal_code, before):
    response = checkout(http, postal_code=postal_code)
    assert response.status_code == 400 and error_code(response) == "validation_error"
    assert field_errors(response, "postal_code")[0]["code"] == "invalid_postal_code"
    assert_nothing_changed(user, before)


@pytest.mark.parametrize("field", Order.DELIVERY_FIELDS)
@pytest.mark.parametrize("value", [1234567890, True, ["x"], {"a": "b"}])
def test_non_string_values_are_rejected(http, user, cart, field, value, before):
    response = checkout(http, **{field: value})
    assert response.status_code == 400 and field_errors(response, field)[0]["code"] == "not_a_string"
    assert_nothing_changed(user, before)


TEXT_FIELDS = ["recipient_name", "province", "city", "address"]
CONTROL_VALUES = [
    "line one\nline two",  # inside
    "trailing\n",  # a trailing newline/tab must be rejected, not silently trimmed away
    "trailing\t",
    "\nleading",
    "\tleading",
    "trailing\r\n",
    "nul\x00inside",
]


def only_field_rejected(response, field, code):
    """The request failed ONLY because of `field` (so no other invalid input or empty cart can explain it)."""
    assert response.status_code == 400 and error_code(response) == "validation_error", response.content
    details = response.json()["error"]["details"]
    assert set(details) == {field}, details
    assert [error["code"] for error in details[field]] == [code]


@pytest.mark.parametrize("field", TEXT_FIELDS)
@pytest.mark.parametrize("value", CONTROL_VALUES)
def test_control_characters_are_rejected_not_trimmed(http, user, cart, field, value, before):
    """Every other field is valid and the cart holds a valid line: the one control character is the only failure."""
    only_field_rejected(checkout(http, **{field: value}), field, "control_characters")
    assert_nothing_changed(user, before)


@pytest.mark.parametrize("value", ["1234567890\n", "1234567890\t", "\n1234567890", "\t1234567890", "12345\n67890"])
def test_postal_code_control_characters_are_rejected_not_trimmed(http, user, cart, value, before):
    only_field_rejected(checkout(http, postal_code=value), "postal_code", "control_characters")
    assert_nothing_changed(user, before)


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_surrounding_spaces_are_trimmed_and_stored_trimmed(http, cart, field):
    response = checkout(http, **{field: "  value  "})
    assert response.status_code == 201, response.content
    assert response.json()[field] == "value" == getattr(Order.objects.get(), field)


def test_validation_errors_never_echo_submitted_values(http, user, cart, before):
    submitted = {
        "recipient_name": "SECRET-NAME-" + "x" * 200,  # max_length
        "province": "SECRET-PROVINCE",  # valid
        "city": "",  # blank
        "address": "SECRET-ADDRESS-\nsecond line",  # control_characters
        "postal_code": "SECRET-POSTAL",  # invalid_postal_code
    }
    response = http.send("post", ORDERS, submitted)
    assert response.status_code == 400 and error_code(response) == "validation_error"
    details = response.json()["error"]["details"]
    # Each marker field really is invalid for the stated reason (province, the valid one, is absent).
    assert {field: [e["code"] for e in errors] for field, errors in details.items()} == {
        "recipient_name": ["max_length"],
        "city": ["blank"],
        "address": ["control_characters"],
        "postal_code": ["invalid_postal_code"],
    }
    text = response.content.decode()
    for marker in ("SECRET-NAME", "SECRET-PROVINCE", "SECRET-ADDRESS", "SECRET-POSTAL"):
        assert marker not in text
    assert_nothing_changed(user, before)


def test_delivery_details_are_not_logged(http, user, cart, before, caplog):
    with caplog.at_level("DEBUG"):
        # Rejected first (only the address is invalid and the cart is full), then accepted.
        only_field_rejected(checkout(http, address="SECRET-STREET-78\nsecond line"), "address", "control_characters")
        assert_nothing_changed(user, before)
        assert checkout(http, address="SECRET-STREET-77").status_code == 201
    assert "SECRET-STREET" not in caplog.text


# --- request bodies that are not a delivery-details object ----------------------------------------

def post_raw(http, raw):
    return http.c.post(ORDERS, data=raw, content_type="application/json", **http._h())


@pytest.mark.parametrize(
    "raw", ["{bad", '{"address": "SECRET-JSON-77", ', "{'address': 'x'}", '{"address": }', "not json"]
)
def test_syntactically_invalid_json_is_a_parse_error_and_changes_nothing(http, user, cart, raw, before):
    response = post_raw(http, raw)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "parse_error"
    assert "details" not in error
    assert "SECRET-JSON-77" not in response.content.decode()  # the parser message never quotes the body
    assert_nothing_changed(user, before)


def test_empty_body_reports_every_required_field_and_changes_nothing(http, user, cart, before):
    response = post_raw(http, "")
    assert response.status_code == 400 and error_code(response) == "validation_error"
    details = response.json()["error"]["details"]
    assert {field: [e["code"] for e in errors] for field, errors in details.items()} == {
        field: ["required"] for field in Order.DELIVERY_FIELDS
    }
    assert_nothing_changed(user, before)


@pytest.mark.parametrize(
    "raw, code",
    [("[]", "invalid"), ('"text"', "invalid"), ("123", "invalid"), ("true", "invalid"), ("null", "null")],
)
def test_valid_json_that_is_not_an_object_is_a_validation_error_and_changes_nothing(
    http, user, cart, raw, code, before
):
    response = post_raw(http, raw)
    assert response.status_code == 400 and error_code(response) == "validation_error", response.content
    details = response.json()["error"]["details"]
    assert set(details) == {"non_field_errors"}, details
    assert [e["code"] for e in details["non_field_errors"]] == [code]
    assert_nothing_changed(user, before)


# --- the shared "nothing changed" helper must itself be able to fail --------------------------------

def _two_line_cart(user):
    a = make_vs(slug="snap-a", stock=5, size_code="m")
    b = make_vs(slug="snap-b", stock=4, size_code="l")
    fill_cart(user, (a, 2), (b, 3))
    return a, b


MUTATIONS = {
    "quantity changed": lambda user, a, b: CartItem.objects.filter(variant_size=b).update(quantity=1),
    "line removed": lambda user, a, b: CartItem.objects.filter(variant_size=a).delete(),
    "line recreated with same quantity": lambda user, a, b: (
        CartItem.objects.filter(variant_size=a).delete(),
        CartItem.objects.create(cart=Cart.objects.get(user=user), variant_size=a, quantity=2),
    ),
    "cart emptied": lambda user, a, b: CartItem.objects.filter(cart__user=user).delete(),
    "cart deleted": lambda user, a, b: Cart.objects.filter(user=user).delete(),
    "stock decremented": lambda user, a, b: VariantSize.objects.filter(pk=b.pk).update(stock_quantity=1),
    "order created": lambda user, a, b: Order.objects.create(
        user=user, customer_phone=user.phone, total=Decimal("1"), **DELIVERY
    ),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_nothing_changed_helper_detects_every_kind_of_change(user, name):
    a, b = _two_line_cart(user)
    before = world(user)
    assert_nothing_changed(user, before)  # untouched state passes
    MUTATIONS[name](user, a, b)
    with pytest.raises(AssertionError):
        assert_nothing_changed(user, before)


def test_nothing_changed_helper_refuses_to_pass_vacuously_on_an_empty_cart(user):
    with pytest.raises(AssertionError, match="vacuous"):
        assert_nothing_changed(user, world(user))


def test_invalid_details_are_reported_before_the_cart_is_considered(http):
    """Documented ordering: details are validated first, so an empty cart + empty body is `validation_error`."""
    response = http.send("post", ORDERS, {})
    assert response.status_code == 400 and error_code(response) == "validation_error"
    assert Order.objects.count() == 0


def test_valid_details_with_empty_cart_is_empty_cart(http):
    response = checkout(http)
    assert response.status_code == 400 and error_code(response) == "empty_cart"


# --- phone: always the account phone -----------------------------------------------------------

def test_delivery_phone_is_the_account_phone_and_cannot_be_overridden(http, user, cart):
    other_number = "09129999999"
    response = checkout(
        http, phone=other_number, recipient_phone=other_number, customer_phone=other_number,
        delivery_phone="+989129999999", contact_phone=other_number,
    )
    assert response.status_code == 201, response.content
    assert Order.objects.get().customer_phone == user.phone == response.json()["customer_phone"]
    text = response.content.decode()
    assert other_number not in text and "989129999999" not in text


def test_phone_snapshot_does_not_change_when_the_account_phone_changes(http, user, cart):
    created = checkout(http).json()
    User.objects.filter(pk=user.pk).update(phone="+989129999999")
    assert Order.objects.get().customer_phone == created["customer_phone"] != "+989129999999"
    assert http.get(f"{ORDERS}{created['id']}/").json()["customer_phone"] == created["customer_phone"]


# --- server-owned values -----------------------------------------------------------------------

def test_client_cannot_set_payment_status_status_total_owner_or_id(http, user, cart):
    response = checkout(
        http, payment_status="paid", status="shipped", total="1", id=999, user=user.id + 1,
        created_at="2000-01-01T00:00:00Z", stock_quantity=1000, unit_price="1",
    )
    assert response.status_code == 201, response.content
    order = Order.objects.get()
    assert (order.payment_status, order.status, order.total) == ("unpaid", "pending", Decimal("2000"))
    assert order.id != 999 and order.user == user and order.created_at.year != 2000
    assert stock_after(cart) == 3  # decremented by the cart quantity, not by anything the client sent


def test_service_ignores_keys_that_are_not_delivery_fields(user, cart):
    order = services.create_order(
        user, {**DELIVERY, "total": Decimal("1"), "payment_status": "paid", "status": "shipped", "user": 0}
    )
    assert (order.total, order.payment_status, order.status, order.user) == (
        Decimal("2000"), "unpaid", "pending", user,
    )


def test_service_requires_every_delivery_field_and_changes_nothing_otherwise(user, cart, before):
    with pytest.raises(KeyError):
        services.create_order(user, {k: v for k, v in DELIVERY.items() if k != "postal_code"})
    assert_nothing_changed(user, before)


# --- authentication, CSRF, ownership (a valid body must not bypass any of them) ----------------

def test_valid_body_does_not_bypass_authentication(user, cart, before):
    anonymous = ApiClient()
    assert anonymous.post(ORDERS, DELIVERY).status_code == 401
    assert_nothing_changed(user, before)


def test_valid_body_does_not_bypass_csrf(http, user, cart, before):
    assert http.api.post(ORDERS, DELIVERY, csrf=False).status_code == 403
    assert_nothing_changed(user, before)


def test_another_customer_cannot_read_my_delivery_details(http, cart):
    created = checkout(http).json()
    stranger = ApiClient()
    stranger.login("09120000002")
    response = stranger.get(f"{ORDERS}{created['id']}/")
    assert response.status_code == 404
    assert DELIVERY["address"] not in response.content.decode()
    assert stranger.get(ORDERS).json() == []
