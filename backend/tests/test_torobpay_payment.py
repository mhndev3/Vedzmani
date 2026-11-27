from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.orders.models import Order, OrderItem, TorobPayPaymentAttempt
from apps.orders.payment_services import PaymentRejected
from apps.orders.torobpay import TorobPayUnavailable
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
    def __init__(
        self, *, eligible=True, provider_status="PENDING", transaction_id=None,
        status_transaction_id=None, verify_transaction_id=None, provider_amount=10000,
    ):
        self.eligible = eligible
        self.provider_status = provider_status
        self.transaction_id = transaction_id
        self.status_transaction_id = status_transaction_id
        self.verify_transaction_id = verify_transaction_id
        self.provider_amount = provider_amount
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
        return {
            "status": self.provider_status,
            "amount": self.provider_amount,
            "transactionId": self.status_transaction_id or self.transaction_id,
        }

    def verify(self, payment_token):
        self.calls.append(("verify", payment_token))
        self.provider_status = "VERIFY"
        return {
            "transactionId": self.verify_transaction_id or self.transaction_id
        }

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
    TOROBPAY_SHIPPING_AMOUNT_TOMAN=None,
    TOROBPAY_CART_ITEM_AMOUNT_MODE="unit",
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

    assert eligibility == {"eligible": True, "amount_rial": 10000}
    assert attempt.amount_toman == 1000
    assert attempt.amount_rial == 10000
    assert attempt.status == TorobPayPaymentAttempt.NEW
    assert attempt.payment_token == "provider-token"
    assert attempt.payment_page_url.startswith("https://cpg.torobpay.com/")
    assert client.payload["amount"] == 10000
    assert client.payload["cartList"][0]["totalAmount"] == 10000
    assert client.payload["cartList"][0]["shippingAmount"] == 0
    assert client.payload["cartList"][0]["taxAmount"] == 0
    assert client.payload["cartList"][0]["isTaxIncluded"] is False
    assert client.payload["cartList"][0]["isShipmentIncluded"] is False
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
    TOROBPAY_CART_ITEM_AMOUNT_MODE="unit",
)
def test_torobpay_does_not_require_shipping_tariff_for_tipax_collect_on_delivery(make_variant_size):
    order, _ = make_order(make_variant_size)
    client = FakeTorobPayClient()

    attempt = initiate_torobpay_payment(
        order,
        return_url="https://vedzmani.ir/api/orders/payment/torobpay/callback/",
        client=client,
    )

    assert attempt.amount_toman == 1000
    assert attempt.amount_rial == 10000
    assert client.payload["cartList"][0]["shippingAmount"] == 0
    assert client.payload["cartList"][0]["isShipmentIncluded"] is False


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
def test_verified_callback_with_insufficient_stock_is_canceled_without_decrement(make_variant_size):
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
    assert [call[0] for call in client.calls].count("cancel") == 1
    assert not any(call[0] == "settle" for call in client.calls)


@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_callback_amount_is_untrusted_when_provider_status_matches(make_variant_size):
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
    assert result == "paid"
    assert order.payment_status == Order.PAID
    assert attempt.status == TorobPayPaymentAttempt.ONGOING
    assert variant_size.stock_quantity == 1
    assert not any(call[0] in {"revert", "cancel"} for call in client.calls)



def test_provider_status_transaction_id_mismatch_pending_never_verifies(make_variant_size):
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
    client = FakeTorobPayClient(
        transaction_id=transaction_id,
        status_transaction_id=str(uuid.uuid4()),
    )

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert result == "pending"
    assert order.payment_status == Order.UNPAID
    assert attempt.status == TorobPayPaymentAttempt.NEW
    assert variant_size.stock_quantity == 2
    assert not any(
        call[0] in {"verify", "settle", "revert", "cancel"}
        for call in client.calls
    )


def test_provider_status_transaction_id_mismatch_after_verify_is_canceled(make_variant_size):
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
    client = FakeTorobPayClient(
        transaction_id=transaction_id,
        provider_status="VERIFY",
        status_transaction_id=str(uuid.uuid4()),
    )

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert result == "failed"
    assert order.payment_status == Order.FAILED
    assert attempt.status == TorobPayPaymentAttempt.CANCELED
    assert attempt.provider_status == "REVERT"
    assert variant_size.stock_quantity == 2
    assert any(call[0] == "cancel" for call in client.calls)
    assert not any(call[0] == "settle" for call in client.calls)

def test_provider_status_amount_mismatch_pending_never_verifies_or_settles(make_variant_size):
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
    client = FakeTorobPayClient(
        transaction_id=transaction_id, provider_amount=9999
    )

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert result == "pending"
    assert order.payment_status == Order.UNPAID
    assert attempt.status == TorobPayPaymentAttempt.NEW
    assert variant_size.stock_quantity == 2
    assert not any(call[0] in {"verify", "settle", "revert", "cancel"} for call in client.calls)


def test_provider_status_amount_mismatch_after_verify_is_canceled(make_variant_size):
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
    client = FakeTorobPayClient(
        transaction_id=transaction_id,
        provider_status="VERIFY",
        provider_amount=9999,
    )

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert result == "failed"
    assert order.payment_status == Order.FAILED
    assert attempt.status == TorobPayPaymentAttempt.CANCELED
    assert variant_size.stock_quantity == 2
    assert [call[0] for call in client.calls].count("cancel") == 1
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


@pytest.mark.django_db(transaction=True)
@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_concurrent_torobpay_payments_cannot_consume_the_same_last_unit(make_variant_size):
    import threading
    from django.db import connection

    variant_size = make_variant_size(stock=1)
    attempts = []
    transaction_ids = {}
    for _ in range(2):
        user = get_user_model().objects.create_user(new_phone())
        order = Order.objects.create(
            user=user,
            customer_phone=user.phone,
            total=Decimal("1000"),
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
            quantity=1,
            subtotal=Decimal("1000"),
        )
        transaction_id = str(uuid.uuid4())
        token = f"provider-token-{len(attempts)}"
        transaction_ids[token] = transaction_id
        attempts.append(TorobPayPaymentAttempt.objects.create(
            order=order,
            merchant_transaction_id=uuid.UUID(transaction_id),
            payment_token=token,
            amount_toman=1000,
            amount_rial=10000,
            status=TorobPayPaymentAttempt.NEW,
        ))

    class ConcurrentClient:
        def __init__(self):
            self.settled = []
            self.reverted = []
            self.states = {token: "PENDING" for token in transaction_ids}

        def status(self, token):
            return {
                "status": self.states[token],
                "amount": 10000,
                "transactionId": transaction_ids[token],
            }

        def verify(self, token):
            self.states[token] = "VERIFY"
            return {"transactionId": transaction_ids[token]}

        def settle(self, token):
            self.settled.append(token)
            self.states[token] = "SETTLE"
            return {"transactionId": transaction_ids[token]}

        def revert(self, token):
            self.reverted.append(token)
            return {"status": "CANCELED"}

        def cancel(self, token):
            self.reverted.append(token)
            return {"status": "CANCELED"}

    client = ConcurrentClient()
    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(index):
        try:
            barrier.wait(timeout=10)
            results[index] = process_torobpay_callback(
                transaction_id=str(attempts[index].merchant_transaction_id),
                state="OK",
                amount="10000",
                client=client,
            )
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    [thread.start() for thread in threads]
    [thread.join(timeout=20) for thread in threads]

    assert sorted(results) == ["out_of_stock", "paid"]
    variant_size.refresh_from_db()
    assert variant_size.stock_quantity == 0
    assert Order.objects.filter(payment_status=Order.PAID).count() == 1
    assert Order.objects.filter(payment_status=Order.FAILED).count() == 1
    assert len(client.settled) == 1
    assert len(client.reverted) == 1


@override_settings(
    ORDERS_ENABLED=True,
    TOROBPAY_ENABLED=True,
    TOROBPAY_SHIPPING_AMOUNT_TOMAN=200,
    TOROBPAY_CART_ITEM_AMOUNT_MODE="",
)
def test_torobpay_token_creation_fails_closed_until_item_amount_semantics_are_confirmed(make_variant_size):
    order, _ = make_order(make_variant_size)
    client = FakeTorobPayClient()

    with pytest.raises(PaymentRejected, match="cart_item_amount_mode_not_configured"):
        initiate_torobpay_payment(
            order,
            return_url="https://vedzmani.ir/api/orders/payment/torobpay/callback/",
            client=client,
        )

    assert client.calls == []


@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_verified_transaction_id_mismatch_is_canceled(make_variant_size):
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
    client = FakeTorobPayClient(
        transaction_id=transaction_id,
        verify_transaction_id=str(uuid.uuid4()),
    )

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert result == "failed"
    assert order.payment_status == Order.FAILED
    assert attempt.status == TorobPayPaymentAttempt.CANCELED
    assert variant_size.stock_quantity == 2
    assert [call[0] for call in client.calls].count("cancel") == 1
    assert not any(call[0] == "settle" for call in client.calls)


@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_verify_identity_mismatch_from_initial_verify_state_is_canceled(make_variant_size):
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
    client = FakeTorobPayClient(
        transaction_id=transaction_id,
        provider_status="VERIFY",
        verify_transaction_id=str(uuid.uuid4()),
    )

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )

    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()
    assert result == "failed"
    assert order.payment_status == Order.FAILED
    assert attempt.status == TorobPayPaymentAttempt.CANCELED
    assert attempt.provider_status == "REVERT"
    assert variant_size.stock_quantity == 2
    assert [call[0] for call in client.calls].count("status") == 2
    assert [call[0] for call in client.calls].count("verify") == 1
    assert [call[0] for call in client.calls].count("cancel") == 1
    assert not any(call[0] == "settle" for call in client.calls)


@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_out_of_stock_reversal_retry_preserves_out_of_stock_outcome(make_variant_size):
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
    original_cancel = client.cancel
    cancel_calls = 0

    def flaky_cancel(payment_token):
        nonlocal cancel_calls
        cancel_calls += 1
        if cancel_calls == 1:
            raise TorobPayUnavailable("provider_unavailable")
        return original_cancel(payment_token)

    client.cancel = flaky_cancel

    first_result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )
    attempt.refresh_from_db()
    assert first_result == "pending"
    assert attempt.status == TorobPayPaymentAttempt.OUT_OF_STOCK

    second_result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )
    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()

    assert second_result == "out_of_stock"
    assert attempt.status == TorobPayPaymentAttempt.CANCELED
    assert order.payment_status == Order.FAILED
    assert variant_size.stock_quantity == 0
    assert cancel_calls == 2
    assert [call[0] for call in client.calls].count("verify") == 1
    assert not any(call[0] == "settle" for call in client.calls)


@override_settings(ORDERS_ENABLED=True, TOROBPAY_ENABLED=True, TOROBPAY_SHIPPING_AMOUNT_TOMAN=0)
def test_settle_timeout_is_reconciled_from_provider_status_without_double_decrement(make_variant_size):
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
    original_settle = client.settle
    settle_calls = 0

    def settle_then_timeout(payment_token):
        nonlocal settle_calls
        settle_calls += 1
        original_settle(payment_token)
        raise TorobPayUnavailable("provider_unavailable")

    client.settle = settle_then_timeout

    result = process_torobpay_callback(
        transaction_id=transaction_id, state="OK", amount="10000", client=client
    )
    order.refresh_from_db()
    attempt.refresh_from_db()
    variant_size.refresh_from_db()

    assert result == "paid"
    assert order.payment_status == Order.PAID
    assert attempt.status == TorobPayPaymentAttempt.ONGOING
    assert attempt.provider_status == "SETTLE"
    assert variant_size.stock_quantity == 1
    assert settle_calls == 1
    assert [call[0] for call in client.calls].count("verify") == 1
    assert [call[0] for call in client.calls].count("status") == 2
