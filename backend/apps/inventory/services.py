"""Stock adjustments: the supported way to change `VariantSize.stock_quantity` outside of order checkout.

One short transaction (`transaction.atomic`), in this order:
  1. validate the input (no database access, so bad input never takes a lock),
  2. lock the `VariantSize` row with SELECT ... FOR UPDATE (`of=("self",)`, the same style as
     `orders.services.create_order`, so adjustments and checkouts serialize on the same row),
  3. compute the new quantity from the *locked, authoritative* database value (a caller never supplies the
     resulting stock, only a signed change) and reject anything that would be negative,
  4. apply a guarded UPDATE (compare-and-set on the locked value, a second line of defence),
  5. insert the `InventoryAdjustment` audit row.
Any exception after step 2 rolls back both the stock change and the audit row. A single row is locked per call, so
there is no lock-ordering concern; a future multi-row operation must lock in primary-key order like checkout does.
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.catalog.models import VariantSize

from .models import REASON_MAX_LENGTH, InventoryAdjustment

MAX_STOCK = 2**31 - 1  # PostgreSQL integer upper bound for the stock / change columns


class InvalidAdjustment(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_adjustment"
    default_detail = _("Invalid stock adjustment.")


class StockWouldGoNegative(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "insufficient_stock"
    default_detail = _("The adjustment would make stock negative.")


def _validated_reason(quantity_change, reason) -> str:
    if isinstance(quantity_change, bool) or not isinstance(quantity_change, int):
        raise InvalidAdjustment(_("quantity_change must be an integer."))
    if quantity_change == 0:
        raise InvalidAdjustment(_("quantity_change must not be zero."))
    if abs(quantity_change) > MAX_STOCK:
        raise InvalidAdjustment(_("quantity_change is out of range."))
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason:
        raise InvalidAdjustment(_("A reason is required."))
    if len(reason) > REASON_MAX_LENGTH:
        raise InvalidAdjustment(_("The reason is too long."))
    return reason


@transaction.atomic
def adjust_stock(*, variant_size_id: int, quantity_change: int, reason: str, created_by=None) -> InventoryAdjustment:
    """Apply a signed `quantity_change` to one variant size and record who/why/when. Returns the audit row."""
    reason = _validated_reason(quantity_change, reason)
    if isinstance(variant_size_id, bool) or not isinstance(variant_size_id, int):
        raise InvalidAdjustment(_("Unknown variant size."))

    try:
        # Lock only the VariantSize row; this is the authoritative quantity for the rest of the transaction.
        locked = VariantSize.objects.select_for_update(of=("self",)).get(pk=variant_size_id)
    except VariantSize.DoesNotExist:
        raise InvalidAdjustment(_("Unknown variant size.")) from None

    new_stock = locked.stock_quantity + quantity_change
    if new_stock < 0:
        raise StockWouldGoNegative()
    if new_stock > MAX_STOCK:
        raise InvalidAdjustment(_("The resulting stock is out of range."))

    updated = VariantSize.objects.filter(pk=locked.pk, stock_quantity=locked.stock_quantity).update(
        stock_quantity=new_stock, updated_at=timezone.now()
    )
    if updated != 1:  # unreachable while the row lock is held; raising rolls the transaction back if it ever isn't
        raise RuntimeError("VariantSize changed while locked; adjustment aborted.")

    return InventoryAdjustment.objects.create(
        variant_size_id=locked.pk,
        quantity_change=quantity_change,
        stock_after=new_stock,
        reason=reason,
        created_by=created_by,
    )
