"""TorobPay payment initiation. All amounts originate from the server-owned order snapshot."""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Order, TorobPayPaymentAttempt
from .payment_services import PaymentRejected
from .torobpay import TorobPayClient, TorobPayError, TorobPayUnavailable


ACTIVE_ATTEMPT_STATUSES = (
    TorobPayPaymentAttempt.INITIATING,
    TorobPayPaymentAttempt.NEW,
    TorobPayPaymentAttempt.IPG,
    TorobPayPaymentAttempt.VERIFY_FOR_W,
    TorobPayPaymentAttempt.SETTLE_FOR_W,
)


def _require_torobpay_ready():
    if not settings.ORDERS_ENABLED or not settings.TOROBPAY_ENABLED:
        raise PaymentRejected("payment_disabled")
    shipping = settings.TOROBPAY_SHIPPING_AMOUNT_TOMAN
    if shipping is None or shipping < 0:
        raise PaymentRejected("shipping_not_configured")
    return shipping


def _rial_from_toman(value):
    amount = Decimal(str(value))
    rial = amount * 10
    if rial != rial.to_integral_value() or rial <= 0:
        raise PaymentRejected("invalid_amount")
    return int(rial)


def _payment_payload(order, attempt, shipping_toman):
    items = list(
        order.items.select_related(
            "variant_size__variant__product__category"
        ).order_by("variant_size_id")
    )
    if not items:
        raise PaymentRejected("empty_order")

    cart_items = []
    for item in items:
        cart_items.append({
            "id": item.sku,
            "name": item.product_name,
            "count": item.quantity,
            "amount": _rial_from_toman(item.unit_price),
            "category": item.variant_size.variant.product.category.name,
        })

    shipping_rial = _rial_from_toman(shipping_toman) if shipping_toman else 0
    return {
        "amount": attempt.amount_rial,
        "paymentMethodTypeDto": "ONLINE_CREDIT",
        "returnURL": attempt._return_url,
        "transactionId": str(attempt.merchant_transaction_id),
        "cartList": [{
            "cartId": str(order.pk),
            "totalAmount": attempt.amount_rial,
            "shippingAmount": shipping_rial,
            "includeShipping": True,
            "cartItems": cart_items,
        }],
        "address": order.address,
        "postalCode": order.postal_code,
        "name_full_customer": order.recipient_name,
        "city": order.city,
        "province": order.province,
        "number_phone_registration": order.customer_phone,
    }


def check_torobpay_eligibility(order, *, client=None):
    shipping_toman = _require_torobpay_ready()
    amount_rial = _rial_from_toman(Decimal(order.total) + Decimal(shipping_toman))
    try:
        response = (client or TorobPayClient()).check_eligibility(amount_rial)
    except TorobPayError as exc:
        raise PaymentRejected(exc.code) from exc
    return {
        "eligible": response["eligible"],
        "amount_rial": amount_rial,
    }


def initiate_torobpay_payment(order, *, return_url, client=None):
    shipping_toman = _require_torobpay_ready()
    if not isinstance(return_url, str) or not return_url.startswith("https://"):
        raise PaymentRejected("invalid_return_url")

    client = client or TorobPayClient()
    failure_code = None
    attempt = None

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.payment_status != Order.UNPAID:
            raise PaymentRejected("order_not_payable")

        cutoff = timezone.now() - timedelta(minutes=10)
        existing = locked_order.torobpay_payment_attempts.filter(
            status__in=ACTIVE_ATTEMPT_STATUSES,
            created_at__gte=cutoff,
        ).order_by("-id").first()
        if existing:
            if existing.payment_page_url:
                return existing
            raise PaymentRejected("payment_initializing")

        amount_toman = int(Decimal(locked_order.total)) + shipping_toman
        amount_rial = _rial_from_toman(amount_toman)
        try:
            eligibility = client.check_eligibility(amount_rial)
        except TorobPayError as exc:
            failure_code = exc.code
        else:
            if eligibility.get("eligible") is not True:
                failure_code = "not_eligible"

        if failure_code is None:
            attempt = TorobPayPaymentAttempt.objects.create(
                order=locked_order,
                merchant_transaction_id=uuid.uuid4(),
                amount_toman=amount_toman,
                amount_rial=amount_rial,
                status=TorobPayPaymentAttempt.INITIATING,
            )
            # The URL is passed separately to avoid persisting arbitrary callback input.
            attempt._return_url = return_url
            payload = _payment_payload(locked_order, attempt, shipping_toman)
            try:
                response = client.create_payment_token(payload)
            except TorobPayUnavailable as exc:
                # The provider may have created a token before the network timed out.
                # Keep INITIATING and block duplicate token creation until reconciliation.
                attempt.last_error_code = exc.code
                attempt.save(update_fields=["last_error_code", "updated_at"])
                failure_code = "provider_unavailable"
            except TorobPayError as exc:
                attempt.status = TorobPayPaymentAttempt.FAILED
                attempt.last_error_code = exc.code[:64]
                attempt.save(update_fields=["status", "last_error_code", "updated_at"])
                failure_code = "provider_rejected"
            else:
                attempt.payment_token = response["paymentToken"]
                attempt.payment_page_url = response["paymentPageUrl"]
                attempt.status = TorobPayPaymentAttempt.NEW
                attempt.save(update_fields=[
                    "payment_token", "payment_page_url", "status", "updated_at"
                ])

    if failure_code:
        raise PaymentRejected(failure_code)
    return attempt
