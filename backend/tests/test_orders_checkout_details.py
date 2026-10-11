"""Checkout delivery details (Agent 11, Session 1): POST /api/orders/ now takes Iranian delivery details.

Browser-like client (sessions + CSRF enforced) against real PostgreSQL, like the other order tests.
The delivery phone is NOT part of the contract: it is the authenticated account's phone (`customer_phone`).
No shipping cost exists: `total` is the sum of the line subtotals only.
"""

from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.accounts.phone import normalize_phone
from apps.orders import services
from apps.orders.models import Order
from apps.orders.serializers import CheckoutSerializer
from tests.conftest import DELIVERY, ApiClient
from tests.test_cart_api import Http, make_vs
from tests.test_orders_api import assert_nothing_changed, checkout, error_code, fill_cart

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
    from apps.catalog.models import VariantSize

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
def test_missing_field_is_rejected_and_changes_nothing(http, user, cart, field):
    response = http.send("post", ORDERS, {k: v for k, v in DELIVERY.items() if k != field})
    assert response.status_code == 400 and error_code(response) == "validation_error"
    assert field_errors(response, field)[0]["code"] == "required"
    assert_nothing_changed(user, [(cart, 5)])


@pytest.mark.parametrize("field", Order.DELIVERY_FIELDS)
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_field_is_rejected_and_changes_nothing(http, user, cart, field, value):
    response = checkout(http, **{field: value})
    assert response.status_code == 400 and error_code(response) == "validation_error"
    assert field_errors(response, field)[0]["code"] == "blank"
    assert_nothing_changed(user, [(cart, 5)])


@pytest.mark.parametrize("field", Order.DELIVERY_FIELDS)
def test_null_field_is_rejected(http, user, cart, field):
    response = checkout(http, **{field: None})
    assert response.status_code == 400 and field_errors(response, field)[0]["code"] == "null"
    assert_nothing_changed(user, [(cart, 5)])


@pytest.mark.parametrize(
    "field, length", [("recipient_name", 121), ("province", 61), ("city", 61), ("address", 256)]
)
def test_over_length_field_is_rejected_and_changes_nothing(http, user, cart, field, length):
    response = checkout(http, **{field: "x" * length})
    assert response.status_code == 400 and field_errors(response, field)[0]["code"] == "max_length"
    assert_nothing_changed(user, [(cart, 5)])


@pytest.mark.parametrize(
    "postal_code",
    ["123456789", "12345678901", "12345-67890", "1234 567890", "12345abcde", "１２３４５６７８９０", "abc"],
)
def test_invalid_postal_code_is_rejected_and_changes_nothing(http, user, cart, postal_code):
    response = checkout(http, postal_code=postal_code)
    assert response.status_code == 400 and error_code(response) == "validation_error"
    assert field_errors(response, "postal_code")[0]["code"] == "invalid_postal_code"
    assert_nothing_changed(user, [(cart, 5)])


@pytest.mark.parametrize("field", Order.DELIVERY_FIELDS)
@pytest.mark.parametrize("value", [1234567890, True, ["x"], {"a": "b"}])
def test_non_string_values_are_rejected(http, user, cart, field, value):
    response = checkout(http, **{field: value})
    assert response.status_code == 400 and field_errors(response, field)[0]["code"] == "not_a_string"
    assert_nothing_changed(user, [(cart, 5)])


@pytest.mark.parametrize("field", ["recipient_name", "province", "city", "address"])
def test_control_characters_are_rejected(http, user, cart, field):
    response = checkout(http, **{field: "line one\nline two"})
    assert response.status_code == 400 and field_errors(response, field)[0]["code"] == "control_characters"
    assert_nothing_changed(user, [(cart, 5)])


def test_postal_code_with_inner_control_character_is_rejected(http, user, cart):
    assert checkout(http, postal_code="12345\n67890").status_code == 400
    assert_nothing_changed(user, [(cart, 5)])


def test_validation_errors_never_echo_submitted_values(http, user, cart):
    submitted = {
        "recipient_name": "SECRET-NAME-" + "x" * 200,  # too long
        "province": "SECRET-PROVINCE",  # valid
        "city": "",  # blank
        "address": "SECRET-ADDRESS-\n",  # control character
        "postal_code": "SECRET-POSTAL",  # invalid
    }
    response = http.send("post", ORDERS, submitted)
    assert response.status_code == 400
    text = response.content.decode()
    for marker in ("SECRET-NAME", "SECRET-PROVINCE", "SECRET-ADDRESS", "SECRET-POSTAL"):
        assert marker not in text
    assert_nothing_changed(user, [(cart, 5)])


def test_delivery_details_are_not_logged(http, cart, caplog):
    with caplog.at_level("DEBUG"):
        assert checkout(http, address="SECRET-STREET-77").status_code == 201
        assert http.send("post", ORDERS, {**DELIVERY, "address": "SECRET-STREET-78\n"}).status_code == 400
    assert "SECRET-STREET" not in caplog.text


@pytest.mark.parametrize("raw", ["", "[]", "null", '"text"', "123"])
def test_missing_or_malformed_body_is_a_client_error_and_changes_nothing(http, user, cart, raw):
    response = http.c.post(ORDERS, data=raw, content_type="application/json", **http._h())
    assert response.status_code == 400, raw
    assert error_code(response) in {"validation_error", "parse_error"}
    assert_nothing_changed(user, [(cart, 5)])


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


def test_service_requires_every_delivery_field_and_changes_nothing_otherwise(user, cart):
    with pytest.raises(KeyError):
        services.create_order(user, {k: v for k, v in DELIVERY.items() if k != "postal_code"})
    assert_nothing_changed(user, [(cart, 5)])


# --- authentication, CSRF, ownership (a valid body must not bypass any of them) ----------------

def test_valid_body_does_not_bypass_authentication(user, cart):
    anonymous = ApiClient()
    assert anonymous.post(ORDERS, DELIVERY).status_code == 401
    assert_nothing_changed(user, [(cart, 5)])


def test_valid_body_does_not_bypass_csrf(http, user, cart):
    assert http.api.post(ORDERS, DELIVERY, csrf=False).status_code == 403
    assert_nothing_changed(user, [(cart, 5)])


def test_another_customer_cannot_read_my_delivery_details(http, cart):
    created = checkout(http).json()
    stranger = ApiClient()
    stranger.login("09120000002")
    response = stranger.get(f"{ORDERS}{created['id']}/")
    assert response.status_code == 404
    assert DELIVERY["address"] not in response.content.decode()
    assert stranger.get(ORDERS).json() == []
