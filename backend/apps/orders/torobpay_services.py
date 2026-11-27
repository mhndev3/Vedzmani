"""TorobPay payment initiation and callback orchestration.

All amounts originate from the server-owned order snapshot. Inventory is changed only
after provider status confirms settlement and while exact variant rows are locked.
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import VariantSize
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


def _require_torobpay_ready(*, require_item_amount_mode=False):
    if not settings.ORDERS_ENABLED or not settings.TOROBPAY_ENABLED:
        raise PaymentRejected("payment_disabled")
    # Tipax freight is paid to the carrier on delivery, not through TorobPay.
    if require_item_amount_mode and settings.TOROBPAY_CART_ITEM_AMOUNT_MODE not in {"unit", "line_total"}:
        raise PaymentRejected("cart_item_amount_mode_not_configured")
    return 0


def _rial_from_toman(value):
    amount = Decimal(str(value))
    rial = amount * 10
    if rial != rial.to_integral_value() or rial <= 0:
        raise PaymentRejected("invalid_amount")
    return int(rial)


def _payment_payload(order, attempt, shipping_toman, return_url):
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
            "amount": _rial_from_toman(
                item.unit_price
                if settings.TOROBPAY_CART_ITEM_AMOUNT_MODE == "unit"
                else item.subtotal
            ),
            "category": item.variant_size.variant.product.category.name,
        })

    shipping_rial = _rial_from_toman(shipping_toman) if shipping_toman else 0
    return {
        "amount": attempt.amount_rial,
        "paymentMethodTypeDto": "ONLINE_CREDIT",
        "returnURL": return_url,
        "transactionId": str(attempt.merchant_transaction_id),
        "cartList": [{
            "cartId": str(order.pk),
            "totalAmount": attempt.amount_rial,
            "taxAmount": 0,
            "shippingAmount": shipping_rial,
            "isTaxIncluded": False,
            "isShipmentIncluded": False,
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
    return {"eligible": response["eligible"], "amount_rial": amount_rial}


def initiate_torobpay_payment(order, *, return_url, client=None):
    shipping_toman = _require_torobpay_ready(require_item_amount_mode=True)
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
            try:
                response = client.create_payment_token(
                    _payment_payload(locked_order, attempt, shipping_toman, return_url)
                )
            except TorobPayUnavailable as exc:
                # Provider may have created a token before the network timed out.
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


def _provider_state(response):
    value = response.get("status") if isinstance(response, dict) else None
    return value if value in {"PENDING", "VERIFY", "SETTLE", "REVERT"} else ""


def _provider_identity_error(response, attempt):
    """Validate amount and merchant transaction identity from provider status."""
    if not isinstance(response, dict):
        return "invalid_provider_status"

    transaction_id = response.get("transactionId")
    if (
        not isinstance(transaction_id, str)
        or transaction_id != str(attempt.merchant_transaction_id)
    ):
        return "transaction_id_mismatch"

    amount = response.get("amount")
    if isinstance(amount, bool):
        return "amount_mismatch"
    try:
        amount = int(str(amount))
    except (TypeError, ValueError):
        return "amount_mismatch"

    if amount != attempt.amount_rial:
        return "amount_mismatch"
    return ""


def _finish_reversal(attempt, client, provider_state):
    """Cancel provider orders that have reached VERIFY/SETTLE; REVERT is already final."""
    try:
        # TorobPay status=VERIFY maps to SETTLE_FOR_W, not VERIFY_FOR_W.
        # The provider only permits /revert for VERIFY_FOR_W; /cancel is valid
        # for SETTLE_FOR_W and ONGOING, so both VERIFY and SETTLE use cancel.
        if provider_state in {"VERIFY", "SETTLE"}:
            client.cancel(attempt.payment_token)
        elif provider_state == "REVERT":
            attempt.status = TorobPayPaymentAttempt.CANCELED
            attempt.save(update_fields=["status", "updated_at"])
            Order.objects.filter(
                pk=attempt.order_id, payment_status=Order.UNPAID
            ).update(payment_status=Order.FAILED, updated_at=timezone.now())
            return True
        else:
            return False
    except TorobPayError as exc:
        # Preserve OUT_OF_STOCK across retryable reversal failures so a later
        # callback retains the original fulfillment outcome.
        if attempt.status != TorobPayPaymentAttempt.OUT_OF_STOCK:
            attempt.status = TorobPayPaymentAttempt.REVERSAL_PENDING
        attempt.last_error_code = exc.code[:64]
        attempt.provider_status = provider_state
        attempt.save(update_fields=["status", "last_error_code", "provider_status", "updated_at"])
        return False

    attempt.status = TorobPayPaymentAttempt.CANCELED
    attempt.provider_status = "REVERT"
    attempt.last_error_code = ""
    attempt.save(update_fields=["status", "provider_status", "last_error_code", "updated_at"])
    Order.objects.filter(
        pk=attempt.order_id, payment_status=Order.UNPAID
    ).update(payment_status=Order.FAILED, updated_at=timezone.now())
    return True


def process_torobpay_callback(*, transaction_id, state, amount, client=None):
    """Treat callback values only as lookup hints; provider status and server amount decide fulfillment."""
    if not isinstance(transaction_id, str) or len(transaction_id) > 64:
        return "unknown"
    try:
        transaction_uuid = uuid.UUID(transaction_id)
    except (ValueError, TypeError, AttributeError):
        return "unknown"
    if state not in {"OK", "FAILED"}:
        return "unknown"

    client = client or TorobPayClient()
    try:
        with transaction.atomic():
            attempt = (
                TorobPayPaymentAttempt.objects.select_for_update()
                .select_related("order")
                .filter(merchant_transaction_id=transaction_uuid)
                .first()
            )
            if attempt is None:
                return "unknown"
            order = Order.objects.select_for_update().get(pk=attempt.order_id)

            if attempt.status == TorobPayPaymentAttempt.ONGOING:
                return "paid" if order.payment_status == Order.PAID else "failed"

            if not attempt.payment_token:
                attempt.return_state = state
                attempt.callback_received_at = timezone.now()
                attempt.last_error_code = "missing_payment_token"
                attempt.save(update_fields=[
                    "return_state", "callback_received_at", "last_error_code", "updated_at"
                ])
                return "pending"

            attempt.return_state = state
            attempt.callback_received_at = timezone.now()
            attempt.save(update_fields=["return_state", "callback_received_at", "updated_at"])

            try:
                status_response = client.status(attempt.payment_token)
            except TorobPayError:
                return "pending"

            provider_state = _provider_state(status_response)
            if not provider_state:
                return "pending"

            identity_error = _provider_identity_error(status_response, attempt)
            if identity_error:
                was_out_of_stock = attempt.status == TorobPayPaymentAttempt.OUT_OF_STOCK
                attempt.provider_status = provider_state
                attempt.last_error_code = identity_error
                if provider_state in {"VERIFY", "SETTLE"} and not was_out_of_stock:
                    attempt.status = TorobPayPaymentAttempt.REVERSAL_PENDING
                attempt.save(update_fields=[
                    "provider_status", "last_error_code", "status", "updated_at"
                ])
                if provider_state in {"VERIFY", "SETTLE"}:
                    if _finish_reversal(attempt, client, provider_state):
                        return "out_of_stock" if was_out_of_stock else "failed"
                return "pending"

            attempt.provider_status = provider_state
            attempt.save(update_fields=["provider_status", "updated_at"])

            # Once a previous callback decided that this payment cannot be fulfilled,
            # retries may only retry its refund/cancel. They must never re-enter settlement.
            if attempt.status in {
                TorobPayPaymentAttempt.REVERSAL_PENDING,
                TorobPayPaymentAttempt.OUT_OF_STOCK,
            }:
                was_out_of_stock = attempt.status == TorobPayPaymentAttempt.OUT_OF_STOCK
                if _finish_reversal(attempt, client, provider_state):
                    return "out_of_stock" if was_out_of_stock else "failed"
                return "pending"

            if provider_state == "PENDING":
                if state != "OK":
                    return "pending"
                try:
                    verified = client.verify(attempt.payment_token)
                except TorobPayError as exc:
                    attempt.last_error_code = exc.code[:64]
                    attempt.save(update_fields=["last_error_code", "updated_at"])
                    return "pending"
                provider_transaction_id = verified.get("transactionId")
                if not isinstance(provider_transaction_id, str) or provider_transaction_id != str(transaction_uuid):
                    # Verify may have advanced the provider to VERIFY. Query state before any reversal.
                    try:
                        mismatch_status = client.status(attempt.payment_token)
                    except TorobPayError:
                        return "pending"
                    provider_state = _provider_state(mismatch_status)
                    status_error = _provider_identity_error(mismatch_status, attempt)
                    if provider_state not in {"VERIFY", "SETTLE"}:
                        return "pending"
                    if status_error:
                        attempt.last_error_code = status_error
                    else:
                        attempt.last_error_code = "transaction_id_mismatch"
                    attempt.provider_status = provider_state
                    attempt.status = TorobPayPaymentAttempt.REVERSAL_PENDING
                    attempt.save(update_fields=[
                        "provider_status", "status", "last_error_code", "updated_at"
                    ])
                    if _finish_reversal(attempt, client, provider_state):
                        return "failed"
                    return "pending"
                attempt.provider_transaction_id = provider_transaction_id
                attempt.verified_at = timezone.now()
                provider_state = "VERIFY"
                attempt.provider_status = provider_state
                attempt.status = TorobPayPaymentAttempt.VERIFY_FOR_W
                attempt.save(update_fields=[
                    "provider_transaction_id", "verified_at", "provider_status", "status", "updated_at"
                ])

            if provider_state == "VERIFY" and not attempt.provider_transaction_id:
                # Recover a callback retry after the provider advanced but the first
                # request could not persist its verified transaction identifier.
                try:
                    verified = client.verify(attempt.payment_token)
                except TorobPayError:
                    return "pending"
                provider_transaction_id = verified.get("transactionId")
                if not isinstance(provider_transaction_id, str) or provider_transaction_id != str(transaction_uuid):
                    # Reconcile provider state before reversing a mismatched verification.
                    try:
                        mismatch_status = client.status(attempt.payment_token)
                    except TorobPayError:
                        return "pending"

                    provider_state = _provider_state(mismatch_status)
                    status_error = _provider_identity_error(mismatch_status, attempt)
                    if provider_state not in {"VERIFY", "SETTLE"}:
                        return "pending"

                    attempt.status = TorobPayPaymentAttempt.REVERSAL_PENDING
                    attempt.provider_status = provider_state
                    attempt.last_error_code = status_error or "transaction_id_mismatch"
                    attempt.save(update_fields=[
                        "status", "provider_status", "last_error_code", "updated_at"
                    ])
                    if _finish_reversal(attempt, client, provider_state):
                        return "failed"
                    return "pending"
                attempt.provider_transaction_id = provider_transaction_id
                attempt.verified_at = timezone.now()
                attempt.save(update_fields=["provider_transaction_id", "verified_at", "updated_at"])

            if provider_state == "REVERT":
                attempt.status = TorobPayPaymentAttempt.CANCELED
                attempt.save(update_fields=["status", "updated_at"])
                if order.payment_status == Order.UNPAID:
                    order.payment_status = Order.FAILED
                    order.save(update_fields=["payment_status", "updated_at"])
                return "failed"

            items = list(order.items.order_by("variant_size_id"))
            locked_variants = {
                row.pk: row
                for row in VariantSize.objects.select_for_update()
                .filter(pk__in=[item.variant_size_id for item in items])
                .order_by("pk")
            }
            has_stock = bool(items) and len(locked_variants) == len(items) and all(
                item.quantity <= locked_variants[item.variant_size_id].stock_quantity
                for item in items
            )
            can_fulfill = (
                order.payment_status == Order.UNPAID
                and has_stock
            )

            if not can_fulfill:
                reason = "out_of_stock" if not has_stock else "payment_not_fulfillable"
                attempt.status = (
                    TorobPayPaymentAttempt.OUT_OF_STOCK
                    if reason == "out_of_stock"
                    else TorobPayPaymentAttempt.REVERSAL_PENDING
                )
                attempt.last_error_code = reason
                attempt.provider_status = provider_state
                attempt.save(update_fields=[
                    "status", "last_error_code", "provider_status", "updated_at"
                ])
                if order.payment_status == Order.UNPAID:
                    order.payment_status = Order.FAILED
                    order.save(update_fields=["payment_status", "updated_at"])
                if _finish_reversal(attempt, client, provider_state):
                    return "out_of_stock" if reason == "out_of_stock" else "failed"
                return "pending"

            if provider_state == "VERIFY":
                attempt.status = TorobPayPaymentAttempt.SETTLE_FOR_W
                attempt.save(update_fields=["status", "updated_at"])
                try:
                    client.settle(attempt.payment_token)
                except TorobPayError as exc:
                    attempt.last_error_code = exc.code[:64]
                    attempt.save(update_fields=["last_error_code", "updated_at"])

                # Always reconcile with provider status, even when settle() returned
                # successfully. Never decrement stock based only on the settle response.
                try:
                    settled_status = client.status(attempt.payment_token)
                except TorobPayError:
                    return "pending"

                provider_state = _provider_state(settled_status)
                status_error = _provider_identity_error(settled_status, attempt)

                if provider_state not in {"VERIFY", "SETTLE"}:
                    return "pending"

                if status_error:
                    attempt.status = TorobPayPaymentAttempt.REVERSAL_PENDING
                    attempt.provider_status = provider_state
                    attempt.last_error_code = status_error
                    attempt.save(update_fields=[
                        "status", "provider_status", "last_error_code", "updated_at"
                    ])
                    if _finish_reversal(attempt, client, provider_state):
                        return "failed"
                    return "pending"

            if provider_state != "SETTLE":
                return "pending"

            # The provider confirms ONGOING. Exact variant rows are still locked;
            # stock changes and the paid order transition commit together.
            for item in items:
                changed = VariantSize.objects.filter(
                    pk=item.variant_size_id,
                    stock_quantity__gte=item.quantity,
                ).update(
                    stock_quantity=F("stock_quantity") - item.quantity,
                    updated_at=timezone.now(),
                )
                if changed != 1:
                    raise PaymentRejected("stock_changed_during_settlement")

            attempt.status = TorobPayPaymentAttempt.ONGOING
            attempt.provider_status = "SETTLE"
            attempt.settled_at = timezone.now()
            attempt.last_error_code = ""
            attempt.save(update_fields=[
                "status", "provider_status", "settled_at", "last_error_code", "updated_at"
            ])
            order.payment_status = Order.PAID
            order.status = Order.CONFIRMED
            order.save(update_fields=["payment_status", "status", "updated_at"])
            return "paid"
    except (TorobPayError, TorobPayUnavailable):
        return "pending"
    except Exception:
        # Any DB-side failure after provider settlement is reconciled on the next callback:
        # the provider status is checked again and stock is only decremented in a fresh atomic commit.
        return "pending"
