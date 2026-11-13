from decimal import Decimal
import threading
from unittest.mock import patch
from urllib.parse import urlencode
import pytest
from django.test import Client, override_settings
from django.db import connection
from django.contrib.auth import get_user_model
from apps.catalog.models import VariantSize
from apps.orders.models import Order, OrderItem, SepPaymentAttempt
from apps.orders.payment_services import initiate_sep_payment, process_sep_callback
from tests.conftest import DELIVERY, new_phone

pytestmark = pytest.mark.django_db

def make_order(make_variant_size, quantity=1, stock=2):
    user = get_user_model().objects.create_user(new_phone())
    vs = make_variant_size(stock=stock)
    order = Order.objects.create(user=user, customer_phone=user.phone, total=Decimal("1000"), **DELIVERY)
    OrderItem.objects.create(order=order, variant_size=vs, product_name=vs.variant.product.name,
        color_name=vs.variant.name, size_label=vs.size.label, sku=vs.sku,
        unit_price=Decimal("1000"), quantity=quantity, subtotal=Decimal("1000") * quantity)
    return order, vs

@override_settings(SEP_PAYMENT_ENABLED=True, SEP_TERMINAL_ID="12345", SEP_SHIPPING_AMOUNT_TOMAN=0)
def test_token_uses_server_amount_converted_from_toman_to_rial(make_variant_size):
    order, vs = make_order(make_variant_size)
    with patch("apps.orders.payment_services.SepClient.request_token", return_value="sep-token") as token:
        attempt = initiate_sep_payment(order, redirect_url="https://vedzmani.ir/api/orders/payment/sep/callback/")
    assert attempt.amount_rial == 10000 and attempt.shipping_amount_toman == 0 and attempt.status == SepPaymentAttempt.PENDING
    assert vs.stock_quantity == 2
    token.assert_called_once_with(amount_rial=10000, res_num=attempt.res_num, redirect_url="https://vedzmani.ir/api/orders/payment/sep/callback/", cell_number=order.customer_phone[3:])

@override_settings(SEP_TERMINAL_ID="12345")
def test_verified_out_of_stock_callback_reverses_payment(make_variant_size):
    order, vs = make_order(make_variant_size, stock=1)
    attempt = SepPaymentAttempt.objects.create(order=order, res_num="VZ-out-stock", shipping_amount_toman=0, amount_rial=10000, token="t", status="pending")
    VariantSize.objects.filter(pk=vs.pk).update(stock_quantity=0)
    verified = {"Success": True, "ResultCode": 0, "TransactionDetail": {
        "RefNum": "ref-out", "TerminalNumber": 12345, "OrginalAmount": 10000,
        "AffectiveAmount": 10000, "RRN": "rrn-out",
    }}
    with patch("apps.orders.payment_services.SepClient.verify", return_value=verified) as verify, patch(
        "apps.orders.payment_services.SepClient.reverse",
        return_value={"Success": True, "ResultCode": 0},
    ) as reverse:
        assert process_sep_callback(res_num=attempt.res_num, ref_num="ref-out") == "out_of_stock"
    verify.assert_called_once_with("ref-out")
    reverse.assert_called_once_with("ref-out")
    order.refresh_from_db(); attempt.refresh_from_db(); vs.refresh_from_db()
    assert order.payment_status == Order.FAILED
    assert attempt.status == SepPaymentAttempt.REVERSED
    assert vs.stock_quantity == 0


@override_settings(SEP_TERMINAL_ID="12345")
def test_out_of_stock_callback_retries_unconfirmed_reversal(make_variant_size):
    order, vs = make_order(make_variant_size, stock=1)
    attempt = SepPaymentAttempt.objects.create(order=order, res_num="VZ-retry-reverse", shipping_amount_toman=0, amount_rial=10000, token="t", status="pending")
    VariantSize.objects.filter(pk=vs.pk).update(stock_quantity=0)
    verified = {"Success": True, "ResultCode": 0, "TransactionDetail": {
        "RefNum": "ref-retry", "TerminalNumber": 12345, "OrginalAmount": 10000,
        "AffectiveAmount": 10000, "RRN": "rrn-retry",
    }}
    with patch("apps.orders.payment_services.SepClient.verify", return_value=verified) as verify, patch(
        "apps.orders.payment_services.SepClient.reverse",
        side_effect=[{"Success": False, "ResultCode": 9}, {"Success": True, "ResultCode": 0}],
    ) as reverse:
        assert process_sep_callback(res_num=attempt.res_num, ref_num="ref-retry") == "pending"
        assert process_sep_callback(res_num=attempt.res_num, ref_num="ref-retry") == "out_of_stock"
    verify.assert_called_once_with("ref-retry")
    assert reverse.call_count == 2
    order.refresh_from_db(); attempt.refresh_from_db()
    assert order.payment_status == Order.FAILED
    assert attempt.status == SepPaymentAttempt.REVERSED

@override_settings(SEP_TERMINAL_ID="12345")
def test_verified_callback_decrements_once_and_replay_is_idempotent(make_variant_size):
    order, vs = make_order(make_variant_size, stock=2)
    attempt = SepPaymentAttempt.objects.create(order=order, res_num="VZ-paid", shipping_amount_toman=0, amount_rial=10000, token="t", status="pending")
    result = {"Success": True, "ResultCode": 0, "TransactionDetail": {
        "RefNum": "ref-paid", "TerminalNumber": 12345, "OrginalAmount": 10000,
        "AffectiveAmount": 10000, "RRN": "rrn-1"}}
    with patch("apps.orders.payment_services.SepClient.verify", return_value=result) as verify:
        assert process_sep_callback(res_num=attempt.res_num, ref_num="ref-paid") == "paid"
        assert process_sep_callback(res_num=attempt.res_num, ref_num="ref-paid") == "paid"
    verify.assert_called_once_with("ref-paid")
    order.refresh_from_db(); attempt.refresh_from_db(); vs.refresh_from_db()
    assert order.payment_status == Order.PAID and order.status == Order.CONFIRMED
    assert attempt.status == SepPaymentAttempt.PAID and vs.stock_quantity == 1

@override_settings(SEP_TERMINAL_ID="12345")
def test_verified_amount_mismatch_triggers_reverse(make_variant_size):
    order, vs = make_order(make_variant_size, stock=2)
    attempt = SepPaymentAttempt.objects.create(order=order, res_num="VZ-bad-amount", shipping_amount_toman=0, amount_rial=10000, token="t", status="pending")
    bad = {"Success": True, "ResultCode": 0, "TransactionDetail": {
        "RefNum": "ref-bad", "TerminalNumber": 12345, "OrginalAmount": 9000, "AffectiveAmount": 9000}}
    with patch("apps.orders.payment_services.SepClient.verify", return_value=bad), patch(
        "apps.orders.payment_services.SepClient.reverse", return_value={"Success": True, "ResultCode": 0}) as reverse:
        assert process_sep_callback(res_num=attempt.res_num, ref_num="ref-bad") == "failed"
    reverse.assert_called_once_with("ref-bad")
    order.refresh_from_db(); attempt.refresh_from_db()
    assert order.payment_status == Order.FAILED and attempt.status == SepPaymentAttempt.REVERSED
    assert vs.stock_quantity == 2


@pytest.mark.django_db(transaction=True)
@override_settings(SEP_TERMINAL_ID="12345")
def test_concurrent_payments_cannot_take_the_same_last_variant_unit(make_variant_size):
    vs = make_variant_size(stock=1)
    attempts = []
    for _ in range(2):
        user = get_user_model().objects.create_user(new_phone())
        order = Order.objects.create(user=user, customer_phone=user.phone, total=Decimal("1000"), **DELIVERY)
        OrderItem.objects.create(order=order, variant_size=vs, product_name=vs.variant.product.name,
            color_name=vs.variant.name, size_label=vs.size.label, sku=vs.sku,
            unit_price=Decimal("1000"), quantity=1, subtotal=Decimal("1000"))
        attempts.append(SepPaymentAttempt.objects.create(
            order=order, res_num=f"VZ-concurrent-{order.pk}", shipping_amount_toman=0,
            amount_rial=10000, token="t", status="pending",
        ))

    barrier = threading.Barrier(2)
    results = [None, None]

    def verify(ref_num):
        return {"Success": True, "ResultCode": 0, "TransactionDetail": {
            "RefNum": ref_num, "TerminalNumber": 12345, "OrginalAmount": 10000,
            "AffectiveAmount": 10000, "RRN": f"rrn-{ref_num}",
        }}

    def worker(index):
        try:
            barrier.wait(timeout=10)
            results[index] = process_sep_callback(
                res_num=attempts[index].res_num, ref_num=f"ref-{index}"
            )
        finally:
            connection.close()

    with patch("apps.orders.payment_services.SepClient.verify", side_effect=verify) as verify_mock, patch(
        "apps.orders.payment_services.SepClient.reverse",
        return_value={"Success": True, "ResultCode": 0},
    ):
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        [thread.start() for thread in threads]
        [thread.join(timeout=15) for thread in threads]

    assert sorted(results) == ["out_of_stock", "paid"]
    # Both charges must be verified; the second callback then sees depleted stock and reverses.
    assert verify_mock.call_count == 2
    assert VariantSize.objects.get(pk=vs.pk).stock_quantity == 0
    assert Order.objects.filter(payment_status=Order.PAID).count() == 1
    assert Order.objects.filter(payment_status=Order.FAILED).count() == 1



@override_settings(SEP_TERMINAL_ID="12345")
def test_failed_verification_retries_ambiguous_reverse_without_verifying_again(make_variant_size):
    order, vs = make_order(make_variant_size, stock=2)
    attempt = SepPaymentAttempt.objects.create(
        order=order, res_num="VZ-retry-invalid", shipping_amount_toman=0,
        amount_rial=10000, token="t", status="pending",
    )
    # SEP says the transaction was collected, but its amount does not match our
    # server-side amount. The payment must never be fulfilled and must be reversed.
    mismatch = {"Success": True, "ResultCode": 0, "TransactionDetail": {
        "RefNum": "ref-retry-invalid", "TerminalNumber": 12345,
        "OrginalAmount": 9000, "AffectiveAmount": 9000,
    }}
    with patch("apps.orders.payment_services.SepClient.verify", return_value=mismatch) as verify, patch(
        "apps.orders.payment_services.SepClient.reverse",
        side_effect=[
            {"Success": False, "ResultCode": 9},
            {"Success": True, "ResultCode": 0},
        ],
    ) as reverse:
        assert process_sep_callback(res_num=attempt.res_num, ref_num="ref-retry-invalid") == "pending"
        attempt.refresh_from_db()
        assert attempt.status == SepPaymentAttempt.REVERSAL_PENDING
        assert process_sep_callback(res_num=attempt.res_num, ref_num="ref-retry-invalid") == "failed"

    verify.assert_called_once_with("ref-retry-invalid")
    assert reverse.call_count == 2
    attempt.refresh_from_db()
    order.refresh_from_db()
    vs.refresh_from_db()
    assert attempt.status == SepPaymentAttempt.REVERSED
    assert order.payment_status == Order.FAILED
    assert vs.stock_quantity == 2


def test_sep_callback_get_is_a_public_non_mutating_readiness_probe():
    response = Client().get("/api/orders/payment/sep/callback/")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response["Cache-Control"].find("no-store") != -1


def test_sep_callback_accepts_provider_form_post_and_returns_customer_to_result_page():
    payload = urlencode({"ResNum": "VZ-callback-test", "RefNum": "ref-callback-test"})
    with patch("apps.orders.views.process_sep_callback", return_value="paid") as process:
        response = Client().post(
            "/api/orders/payment/sep/callback/",
            data=payload,
            content_type="application/x-www-form-urlencoded",
        )
    process.assert_called_once_with(res_num="VZ-callback-test", ref_num="ref-callback-test")
    assert response.status_code == 302
    assert response["Location"] == "/fa/checkout/payment-result?status=success"

@override_settings(SEP_TERMINAL_ID="12345")
def test_second_successful_attempt_for_paid_order_is_reversed_without_second_fulfillment(make_variant_size):
    order, vs = make_order(make_variant_size, stock=3)
    first = SepPaymentAttempt.objects.create(
        order=order, res_num="VZ-first-charge", shipping_amount_toman=0,
        amount_rial=10000, token="first", status=SepPaymentAttempt.PENDING,
    )
    second = SepPaymentAttempt.objects.create(
        order=order, res_num="VZ-second-charge", shipping_amount_toman=0,
        amount_rial=10000, token="second", status=SepPaymentAttempt.PENDING,
    )
    verified = lambda ref: {"Success": True, "ResultCode": 0, "TransactionDetail": {
        "RefNum": ref, "TerminalNumber": 12345, "OrginalAmount": 10000,
        "AffectiveAmount": 10000, "RRN": f"rrn-{ref}",
    }}
    with patch("apps.orders.payment_services.SepClient.verify", side_effect=verified) as verify, patch(
        "apps.orders.payment_services.SepClient.reverse",
        return_value={"Success": True, "ResultCode": 0},
    ) as reverse:
        assert process_sep_callback(res_num=first.res_num, ref_num="ref-first") == "paid"
        assert process_sep_callback(res_num=second.res_num, ref_num="ref-second") == "failed"

    assert verify.call_count == 2
    reverse.assert_called_once_with("ref-second")
    order.refresh_from_db(); first.refresh_from_db(); second.refresh_from_db(); vs.refresh_from_db()
    assert order.payment_status == Order.PAID and order.status == Order.CONFIRMED
    assert first.status == SepPaymentAttempt.PAID and first.ref_num == "ref-first"
    assert second.status == SepPaymentAttempt.REVERSED and second.ref_num == "ref-second"
    assert vs.stock_quantity == 2


@override_settings(SEP_TERMINAL_ID="12345")
def test_refnum_owned_by_another_attempt_is_not_reversed(make_variant_size):
    order, vs = make_order(make_variant_size, stock=2)
    first = SepPaymentAttempt.objects.create(
        order=order, res_num="VZ-ref-owner", ref_num="ref-shared", shipping_amount_toman=0,
        amount_rial=10000, token="first", status=SepPaymentAttempt.PAID,
    )
    second = SepPaymentAttempt.objects.create(
        order=order, res_num="VZ-ref-replay", shipping_amount_toman=0,
        amount_rial=10000, token="second", status=SepPaymentAttempt.PENDING,
    )
    order.payment_status = Order.PAID
    order.status = Order.CONFIRMED
    order.save(update_fields=["payment_status", "status", "updated_at"])
    with patch("apps.orders.payment_services.SepClient.verify") as verify, patch(
        "apps.orders.payment_services.SepClient.reverse"
    ) as reverse:
        assert process_sep_callback(res_num=second.res_num, ref_num="ref-shared") == "failed"
    verify.assert_not_called()
    reverse.assert_not_called()
    second.refresh_from_db()
    assert second.status == SepPaymentAttempt.PENDING and second.ref_num is None
    assert first.status == SepPaymentAttempt.PAID
    assert vs.stock_quantity == 2

