from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.orders.models import Order, OrderItem, TorobPayPaymentAttempt
from apps.orders.payment_services import PaymentRejected
from apps.orders.torobpay_services import (
    check_torobpay_eligibility,
    initiate_torobpay_payment,
    process_torobpay_callback,
)
from tests.conftest import DELIVERY, new_phone


pytestmark = pytest.mark.django_db


def make_order(make_variant_size, *, stock=2, quantity=1):
    user = get_user_model().objects.create_user(new_phone())
    variant_size = make_variant_size(stock=stock)
    order = Order.objects.create(
        user=user,
        customer_phone=user.phone,
        total=Decimal("1000") * quantity,
        **DELIVERY,
    )
    OrderItem.objects.create(
        order=order,
        variant_size=variant_size,
        product_name=variant_size.variant.product.name,
        color_name=variant_size.variant.name,
        size_label=variant_size.size.label,
        sku=variant_size.sku,
        unit_price=Decimal("1000"),
        quantity=quantity,
        subtotal=Decimal("1000") * quantity,
    )
    return order, variant_size


class FakeTorobPayClient:
    def __init__(self, *, eligible=True, provider_status="PENDING", transaction_id=None):
        self.eligible = eligible
        self.provider_status = provider_status
        self.transaction_id = transaction_id
        self.payload = None
        self.calls = []

    def check_eligibility(self, amount_rial):
        self.calls.append(("eligibility", amount_rial))
        return {"eligible": self.eligible}

    def create_payment_token(self, payload):
        self.payload = payload
        self.calls.append(("create_token", payload))
        return {
            "paymentToken": "provider-token",
            "paymentPageUrl": "https://cpg.torobpay.com/payment/provider-token",
        }

    def status(self, payment_token):
        self.calls.append(("status", payment_token))
        return {"status": self.provider_status}

    def verify(self, payment_token):
        self.calls.append(("verify", payment_token))
        return {"transactionId": self.transaction_id}

    def settle(self, payment_token):
        self.calls.append(("settle", payment_token))
        self.provider_status = "SETTLE"
        return {"transactionId": self.transaction_id}

    def revert(self, payment_token):
        self.calls.append(("revert", payment_token))
        self.provider_status = "REVERT"
        return {"status": "CANCELED"}

    def cancel(self, payment_token):
        self.calls.append(("cancel", payment_token))
        self.provider_status = "REVERT"
        return {"status": "CANCELED"}


@override_settings(
    ORDERS_ENABLED=True,
    TOROBPAY_ENABLED=True,
    TOROBPAY_SHIPPING_AMOUNT_TOMAN=200,
)
def test_torobpay_eligibility_and_token_use_server_owned_rial_amount(make_variant_size):
    order, variant_size = make_order(make_variant_size)
    client = FakeTorobPayClient()

    eligibility = check_torobpay_eligibility(order, client=client)
    attempt = initiate_torobpay_payment(
        order,
        return_url="https://vedzmani.ir/api/orders/payment/torobpay/callback/",
        client=client,
    )

    assert eligibility == {"eligible": True, "amount_rial": 12000}
    assert attempt.amount_toman == 1200
    assert attempt.amount_rial == 12000
    assert attempt.status == TorobPayPaymentAttempt.NEW
    assert attempt.payment_token == "provider-token"
    assert attempt.payment_page_url.startswith("https://cpg.torobpay.com/")
    assert client.payload["amount"] == 12000
    assert client.payload["cartList"][0]["totalAmount"] == 12000
    assert client.payload["cartList"][0]["shippingAmount"] == 2000
    assert client.payload["cartList"][0]["cartItems"][0]["amount"] == 10000
    assert client.payload["transactionId"] == str(attempt.merchant_transaction_id)
    assert client.payload["number_phone_registration"] == order.customer_phone
    assert variant_size.stock_quantity == 2


@override_settings(
    ORDERS_ENABLED=False,
    TOROBPAY_ENABLED=True,
    TOROBPAY_SHIPPING_AMOUNT_TOMAN=0,
)
def test_torobpay_initiation_fails_closed_when_orders_are_disabled(make_variant_size):
    order, _ = make_order(make_variant_size)
    client = FakeTorobPayClient()

    with pytest.raises(PaymentRejected, match="payment_disabled"):
        initiate_torobpay_payment(
            order,
            return_url="https://vedzmani.ir/api/orders/payment/torobpay/callback/",
            client=client,
        )

    assert client.calls == []


@override_settings(
    ORDERS_ENABLED=True,
    TOROBPAY_ENABLED=True,
    TOROBPAY_SHIPPING_AMOUNT_TOMAN=None,
)
def test_torobpay_initiation_fails_closed_until_shipping_is_configured(make_variant_size):
    order, _ = make_order(make_variant_size)
    client = FakeTorobPayClient()

    with pytest.raises(PaymentRejected, match="shipping_not_configured"):
        initiate_torobpay_payment(
            order,
            return_url="https://vedzmani.ir/api/orders/payment/torobpay/callback/",
            client=client,
        )

    assert client.calls == []


@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_verified_and_settled_callback_decrements_stock_once(make_variant_size):
    order, variant_size = make_order(make_variant_size, stock=2)
    transaction_id = str(uuid.uuid4())
    attempt = TorobPayPaymentAttempt.objects.create(
        order=order,
        merchant_transaction_id=uuid.UUID(transaction_id),
        payment_token="provider-token",
        amount_toman=1000,
        amount_rial=10000,
        status=TorobPayPaymentAttempt.NEW,
    )
    client = FakeTorobPayClient(transaction_id=transaction_id)

    assert process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    ) == "paid"
    assert process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    ) == "paid"

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert order.payment_status == Order.PAID
    assert order.status == Order.CONFIRMED
    assert attempt.status == TorobPayPaymentAttempt.ONGOING
    assert variant_size.stock_quantity == 1
    assert [call[0] for call in client.calls].count("verify") == 1
    assert [call[0] for call in client.calls].count("settle") == 1


@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_verified_callback_with_insufficient_stock_is_reverted_without_decrement(make_variant_size):
    order, variant_size = make_order(make_variant_size, stock=0)
    transaction_id = str(uuid.uuid4())
    attempt = TorobPayPaymentAttempt.objects.create(
        order=order,
        merchant_transaction_id=uuid.UUID(transaction_id),
        payment_token="provider-token",
        amount_toman=1000,
        amount_rial=10000,
        status=TorobPayPaymentAttempt.NEW,
    )
    client = FakeTorobPayClient(transaction_id=transaction_id)

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert result == "out_of_stock"
    assert order.payment_status == Order.FAILED
    assert attempt.status == TorobPayPaymentAttempt.CANCELED
    assert variant_size.stock_quantity == 0
    assert [call[0] for call in client.calls].count("revert") == 1
    assert not any(call[0] == "settle" for call in client.calls)


@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_callback_amount_mismatch_is_reverted_and_never_fulfills(make_variant_size):
    order, variant_size = make_order(make_variant_size, stock=2)
    transaction_id = str(uuid.uuid4())
    attempt = TorobPayPaymentAttempt.objects.create(
        order=order,
        merchant_transaction_id=uuid.UUID(transaction_id),
        payment_token="provider-token",
        amount_toman=1000,
        amount_rial=10000,
        status=TorobPayPaymentAttempt.NEW,
    )
    client = FakeTorobPayClient(transaction_id=transaction_id)

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="9999", client=client
    )

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert result == "failed"
    assert order.payment_status == Order.FAILED
    assert attempt.status == TorobPayPaymentAttempt.CANCELED
    assert variant_size.stock_quantity == 2
    assert [call[0] for call in client.calls].count("revert") == 1
    assert not any(call[0] == "settle" for call in client.calls)


def test_torobpay_callback_accepts_provider_form_post_and_redirects_safely():
    from urllib.parse import urlencode
    from unittest.mock import patch
    from django.test import Client

    transaction_id = str(uuid.uuid4())
    payload = urlencode({
        "transactionId": transaction_id,
        "state": "OK",
        "amount": "10000",
    })
    with patch(
        "apps.orders.views.process_torobpay_callback",
        return_value="paid",
    ) as process:
        response = Client().post(
            "/api/orders/payment/torobpay/callback/",
            data=payload,
            content_type="application/x-www-form-urlencoded",
        )

    process.assert_called_once_with(
        transaction_id=transaction_id,
        state="OK",
        amount="10000",
    )
    assert response.status_code == 302
    assert response["Location"] == "/fa/checkout/payment-result?status=success"


def test_torobpay_callback_get_is_non_mutating_readiness_probe():
    from django.test import Client

    response = Client().get("/api/orders/payment/torobpay/callback/")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert "no-store" in response["Cache-Control"]
