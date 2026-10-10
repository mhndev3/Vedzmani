"""Order creation business logic. The view stays thin; checkout is ONE atomic transaction.

Order of operations (all inside `transaction.atomic`, any exception rolls everything back):
  1. lock the caller's Cart row (serializes double submits: the loser finds an empty cart),
  2. lock every purchased `VariantSize` row with SELECT ... FOR UPDATE, always in primary-key order so two
     concurrent checkouts can never deadlock on each other,
  3. revalidate from the locked rows: still purchasable (whole catalog chain active) and stock sufficient,
  4. snapshot names/SKU/price from the locked rows, compute totals, decrement stock, create order + items,
  5. delete the cart's lines.
Prices are never read from the client or from the cart (the cart stores none).
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.cart.models import Cart
from apps.cart.services import InsufficientStock, ItemUnavailable, purchasable_variant_sizes
from apps.catalog.models import VariantSize

from .models import Order, OrderItem


class EmptyCart(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "empty_cart"
    default_detail = _("The cart is empty.")


def _clear_cart(cart: Cart) -> None:
    cart.items.all().delete()
    cart.save(update_fields=["updated_at"])


@transaction.atomic
def create_order(user) -> Order:
    cart = Cart.objects.select_for_update().filter(user=user).first()
    cart_items = list(cart.items.order_by("variant_size_id")) if cart is not None else []
    if not cart_items:
        raise EmptyCart()

    # Lock only the VariantSize rows (of=self); the joined product/color/size rows are just read.
    locked = {
        vs.pk: vs
        for vs in purchasable_variant_sizes()
        .select_related("size", "variant__product")
        .select_for_update(of=("self",))
        .filter(pk__in=[i.variant_size_id for i in cart_items])
        .order_by("pk")
    }

    # Whole order is rejected (nothing written) if any line is gone/unpublished, then if any lacks stock.
    if any(i.variant_size_id not in locked for i in cart_items):
        raise ItemUnavailable()
    if any(i.quantity > locked[i.variant_size_id].stock_quantity for i in cart_items):
        raise InsufficientStock()

    lines = []
    total = Decimal("0")
    for item in cart_items:
        vs = locked[item.variant_size_id]
        product = vs.variant.product
        unit_price = product.current_price
        subtotal = unit_price * item.quantity
        total += subtotal
        lines.append((item, vs, product, unit_price, subtotal))

    now = timezone.now()
    for item, vs, *_rest in lines:
        # Guarded decrement: belt and braces on top of the row lock (never lets stock go negative).
        updated = VariantSize.objects.filter(pk=vs.pk, stock_quantity__gte=item.quantity).update(
            stock_quantity=F("stock_quantity") - item.quantity, updated_at=now
        )
        if updated != 1:
            raise InsufficientStock()

    order = Order.objects.create(user=user, customer_phone=user.phone, total=total)
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                variant_size=vs,
                product_name=product.name,
                color_name=vs.variant.name,
                size_label=vs.size.label,
                sku=vs.sku,
                unit_price=unit_price,
                quantity=item.quantity,
                subtotal=subtotal,
            )
            for item, vs, product, unit_price, subtotal in lines
        ]
    )
    _clear_cart(cart)
    return order
