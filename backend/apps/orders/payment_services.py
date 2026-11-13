"""SEP payment orchestration. Inventory and payment confirmation commit together."""
import uuid
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.catalog.models import VariantSize
from .models import Order, SepPaymentAttempt
from .sep import SepClient, SepError, SepUnavailable

class PaymentRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def initiate_sep_payment(order, *, redirect_url):
    if not settings.ORDERS_ENABLED or not settings.SEP_PAYMENT_ENABLED:
        raise PaymentRejected("payment_disabled")
    if settings.SEP_SHIPPING_AMOUNT_TOMAN is None or settings.SEP_SHIPPING_AMOUNT_TOMAN < 0:
        raise PaymentRejected("shipping_not_configured")
    if not settings.SEP_TERMINAL_ID:
        raise PaymentRejected("payment_not_configured")
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.payment_status != Order.UNPAID:
            raise PaymentRejected("order_not_payable")
        existing = locked_order.sep_payment_attempts.filter(
            status=SepPaymentAttempt.PENDING, created_at__gte=timezone.now() - timedelta(minutes=20)
        ).order_by("-id").first()
        if existing and existing.token:
            return existing
        res_num = f"VZ{locked_order.pk}-{uuid.uuid4().hex[:16]}"
        shipping_toman = settings.SEP_SHIPPING_AMOUNT_TOMAN
        amount_rial = int((Decimal(locked_order.total) + Decimal(shipping_toman)) * 10)
        attempt = SepPaymentAttempt.objects.create(
            order=locked_order, res_num=res_num, shipping_amount_toman=shipping_toman, amount_rial=amount_rial,
            status=SepPaymentAttempt.INITIATING,
        )
        token = SepClient().request_token(
            amount_rial=amount_rial, res_num=res_num, redirect_url=redirect_url,
            cell_number=locked_order.customer_phone[3:],
        )
        attempt.token, attempt.status = token, SepPaymentAttempt.PENDING
        attempt.save(update_fields=["token", "status", "updated_at"])
        return attempt

def _verified_detail(response, attempt, ref_num):
    detail = response.get("TransactionDetail")
    if response.get("Success") is not True or response.get("ResultCode") != 0 or not isinstance(detail, dict):
        return False, detail if isinstance(detail, dict) else {}
    try:
        valid = (
            str(detail.get("RefNum")) == ref_num
            and int(detail.get("TerminalNumber")) == int(settings.SEP_TERMINAL_ID)
            and int(detail.get("OrginalAmount")) == attempt.amount_rial
            and int(detail.get("AffectiveAmount")) == attempt.amount_rial
        )
    except (TypeError, ValueError):
        valid = False
    return valid, detail

def process_sep_callback(*, res_num, ref_num):
    if not res_num or not ref_num or len(res_num) > 40 or len(ref_num) > 80:
        return "unknown"
    verified_ref = False
    reverse_needed = False
    outcome = "failed"
    try:
        with transaction.atomic():
            attempt = SepPaymentAttempt.objects.select_for_update().select_related("order").filter(res_num=res_num).first()
            if attempt is None:
                return "unknown"
            if attempt.status == SepPaymentAttempt.PAID:
                return "paid" if attempt.ref_num == ref_num else "failed"
            if attempt.status == SepPaymentAttempt.REVERSED:
                return "reversed" if attempt.ref_num == ref_num else "failed"
            if attempt.status == SepPaymentAttempt.FAILED:
                return "failed"
            if attempt.status == SepPaymentAttempt.REVERSAL_PENDING:
                if attempt.ref_num != ref_num:
                    return "failed"
                reverse_needed = True
                outcome = "failed"
            elif attempt.status == SepPaymentAttempt.OUT_OF_STOCK:
                # A previous reversal may have failed or timed out. A repeated provider
                # callback retries the reversal without verifying or fulfilling the order again.
                if attempt.ref_num != ref_num:
                    return "failed"
                reverse_needed = True
                outcome = "out_of_stock"
            else:
                order = Order.objects.select_for_update().get(pk=attempt.order_id)
                if attempt.ref_num and attempt.ref_num != ref_num:
                    return "failed"
                if order.payment_status != Order.UNPAID:
                    # A different SEP attempt can still have been collected after an
                    # earlier attempt paid (or failed). Never fulfill it or consume stock;
                    # verify the provider reference and reverse any collected second charge.
                    other_owner = SepPaymentAttempt.objects.filter(ref_num=ref_num).exclude(pk=attempt.pk).first()
                    if other_owner:
                        # This RefNum is already owned by another attempt. Do not reverse
                        # a transaction that may be the legitimate payment for that attempt.
                        return "failed"
                    response = SepClient().verify(ref_num)
                    verified, detail = _verified_detail(response, attempt, ref_num)
                    code = response.get("ResultCode") if isinstance(response, dict) else None
                    attempt.provider_result_code = code if isinstance(code, int) else None
                    collected = verified or (
                        isinstance(response, dict) and (
                            (response.get("Success") is True and response.get("ResultCode") == 0)
                            or response.get("ResultCode") == 2
                        )
                    )
                    if collected:
                        attempt.ref_num = ref_num
                        attempt.status = SepPaymentAttempt.REVERSAL_PENDING
                        attempt.save(update_fields=["ref_num", "provider_result_code", "status", "updated_at"])
                        verified_ref = True
                        reverse_needed = True
                    else:
                        attempt.status = SepPaymentAttempt.FAILED
                        attempt.save(update_fields=["provider_result_code", "status", "updated_at"])
                    outcome = "failed"
                else:
                    attempt.ref_num = ref_num
                    attempt.save(update_fields=["ref_num", "updated_at"])
                items = list(order.items.order_by("variant_size_id"))
                locked = {
                    row.pk: row for row in VariantSize.objects.select_for_update()
                    .filter(pk__in=[item.variant_size_id for item in items]).order_by("pk")
                }

                # Verify with SEP before deciding whether stock shortage requires a refund.
                # The callback's RefNum alone is never proof that money was collected.
                response = SepClient().verify(ref_num)
                verified, detail = _verified_detail(response, attempt, ref_num)
                code = response.get("ResultCode") if isinstance(response, dict) else None
                attempt.provider_result_code = code if isinstance(code, int) else None
                if not verified:
                    if isinstance(response, dict) and (
                        (response.get("Success") is True and response.get("ResultCode") == 0)
                        or response.get("ResultCode") == 2
                    ):
                        # SEP may report a duplicate Verify after an earlier successful
                        # charge. Without complete matching details, never fulfill it.
                        verified_ref = True
                        reverse_needed = True
                    attempt.status = (
                        SepPaymentAttempt.REVERSAL_PENDING if reverse_needed else SepPaymentAttempt.FAILED
                    )
                    attempt.save(update_fields=["provider_result_code", "status", "updated_at"])
                    order.payment_status = Order.FAILED
                    order.save(update_fields=["payment_status", "updated_at"])
                    outcome = "failed"
                else:
                    verified_ref = True
                    rrn = detail.get("RRN")
                    attempt.provider_rrn = str(rrn)[:40] if rrn else ""
                    has_stock = len(locked) == len(items) and all(
                        item.quantity <= locked[item.variant_size_id].stock_quantity for item in items
                    )
                    if not has_stock:
                        # SEP confirmed collection, but inventory cannot fulfill this order.
                        # Keep OUT_OF_STOCK until ReverseTransaction is confirmed so a later
                        # callback can retry a failed/ambiguous reversal.
                        attempt.status = SepPaymentAttempt.OUT_OF_STOCK
                        attempt.save(update_fields=["provider_result_code", "provider_rrn", "status", "updated_at"])
                        order.payment_status = Order.FAILED
                        order.save(update_fields=["payment_status", "updated_at"])
                        reverse_needed = True
                        outcome = "out_of_stock"
                    else:
                        for item in items:
                            changed = VariantSize.objects.filter(
                                pk=item.variant_size_id, stock_quantity__gte=item.quantity
                            ).update(stock_quantity=F("stock_quantity") - item.quantity, updated_at=timezone.now())
                            if changed != 1:
                                reverse_needed = True
                                raise PaymentRejected("stock_changed_during_payment")
                        attempt.status = SepPaymentAttempt.PAID
                        attempt.save(update_fields=["provider_result_code", "provider_rrn", "status", "updated_at"])
                        order.payment_status, order.status = Order.PAID, Order.CONFIRMED
                        order.save(update_fields=["payment_status", "status", "updated_at"])
                        outcome = "paid"
    except SepUnavailable:
        return "pending"
    except Exception:
        if verified_ref or reverse_needed:
            # Persist an explicit retryable state before contacting SEP. If the reverse
            # request times out or the process dies, a repeated callback can retry it.
            SepPaymentAttempt.objects.filter(res_num=res_num).exclude(
                status__in=[SepPaymentAttempt.PAID, SepPaymentAttempt.REVERSED]
            ).update(ref_num=ref_num, status=SepPaymentAttempt.REVERSAL_PENDING)
            try:
                reversed_result = SepClient().reverse(ref_num)
                if reversed_result.get("Success") is True and reversed_result.get("ResultCode") == 0:
                    SepPaymentAttempt.objects.filter(res_num=res_num, ref_num=ref_num).update(status=SepPaymentAttempt.REVERSED)
            except SepError:
                pass
        return "failed"
    if reverse_needed:
        try:
            reversed_result = SepClient().reverse(ref_num)
            if reversed_result.get("Success") is True and reversed_result.get("ResultCode") == 0:
                SepPaymentAttempt.objects.filter(res_num=res_num, ref_num=ref_num).update(status=SepPaymentAttempt.REVERSED)
                return "out_of_stock" if outcome == "out_of_stock" else outcome
        except SepError:
            pass
        # Do not tell the customer the refund completed when SEP did not confirm it.
        # Keep OUT_OF_STOCK for a safe retry on the next callback.
        return "pending"
    return outcome
