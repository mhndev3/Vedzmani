"""Cart business logic. Views stay thin; every mutation is one short transaction.

Stock rule: the cart is NOT a reservation. We read `stock_quantity` (no lock, no write) to reject
quantities that cannot currently be fulfilled; checkout must validate again under its own locks.
Concurrency rule: each mutation locks the *user's own cart row* (SELECT ... FOR UPDATE), which
serializes that user's concurrent requests so the quantity/line limits cannot be bypassed.
Reads take no locks.
"""

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, ErrorDetail, NotFound, ValidationError

from apps.catalog.models import VariantImage, VariantSize

from .models import Cart, CartItem

MAX_BIGINT = 2**63 - 1


class InsufficientStock(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "insufficient_stock"
    default_detail = _("Requested quantity is not available.")


class ItemUnavailable(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "item_unavailable"
    default_detail = _("This item is no longer available.")


class CartFull(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "cart_full"
    default_detail = _("The cart cannot hold more distinct items.")


def purchasable_variant_sizes():
    """VariantSize rows that are published and sellable (whole catalog chain active)."""
    return VariantSize.objects.filter(
        is_active=True,
        variant__is_active=True,
        variant__product__is_active=True,
        variant__product__category__is_active=True,
    )


def _quantity_error(code: str, message: str) -> ValidationError:
    return ValidationError({"quantity": [ErrorDetail(message, code=code)]})


def _check_quantity(quantity: int, stock_quantity: int) -> None:
    if quantity > settings.CART_MAX_ITEM_QUANTITY:
        raise _quantity_error("max_quantity", f"At most {settings.CART_MAX_ITEM_QUANTITY} units per item.")
    if quantity > stock_quantity:
        raise InsufficientStock()


def _locked_cart(user) -> Cart:
    """Get-or-create (race-safe via UNIQUE user) then lock the row for this transaction."""
    cart, _created = Cart.objects.get_or_create(user=user)
    return Cart.objects.select_for_update().get(pk=cart.pk)


def _touch(cart: Cart) -> None:
    cart.save(update_fields=["updated_at"])


@transaction.atomic
def add_item(user, variant_size_id: int, quantity: int) -> None:
    """Add `quantity` units; an existing line for the same VariantSize is incremented."""
    cart = _locked_cart(user)
    # Unknown, inactive and unpublished are indistinguishable to the client on purpose.
    variant_size = purchasable_variant_sizes().filter(pk=variant_size_id).first()
    if variant_size is None:
        raise ValidationError(
            {"variant_size_id": [ErrorDetail("This item is not available.", code="unavailable")]}
        )
    item = CartItem.objects.filter(cart=cart, variant_size=variant_size).first()
    if item is None:
        if cart.items.count() >= settings.CART_MAX_LINES:
            raise CartFull()
        _check_quantity(quantity, variant_size.stock_quantity)
        CartItem.objects.create(cart=cart, variant_size=variant_size, quantity=quantity)
    else:
        new_quantity = item.quantity + quantity
        _check_quantity(new_quantity, variant_size.stock_quantity)
        item.quantity = new_quantity
        item.save(update_fields=["quantity", "updated_at"])
    _touch(cart)


@transaction.atomic
def set_item_quantity(user, item_id: int, quantity: int) -> None:
    cart = _locked_cart(user)
    item = _own_item(cart, item_id)
    variant_size = purchasable_variant_sizes().filter(pk=item.variant_size_id).first()
    if variant_size is None:
        raise ItemUnavailable()  # the client may still remove it
    _check_quantity(quantity, variant_size.stock_quantity)
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    _touch(cart)


@transaction.atomic
def remove_item(user, item_id: int) -> None:
    cart = _locked_cart(user)
    _own_item(cart, item_id).delete()
    _touch(cart)


@transaction.atomic
def clear_cart(user) -> None:
    cart = Cart.objects.select_for_update().filter(user=user).first()
    if cart is not None:
        cart.items.all().delete()
        _touch(cart)


def _own_item(cart: Cart, item_id: int) -> CartItem:
    # Scoped to the caller's cart: another user's item id is indistinguishable from a missing one.
    if item_id > MAX_BIGINT:
        raise NotFound()
    item = CartItem.objects.filter(cart=cart, pk=item_id).first()
    if item is None:
        raise NotFound()
    return item


# --- read side ---------------------------------------------------------------------------------

def _availability(item: CartItem) -> str:
    vs = item.variant_size
    live = vs.is_active and vs.variant.is_active and vs.variant.product.is_active and vs.variant.product.category.is_active
    if not live:
        return "unavailable"
    return "available" if item.quantity <= vs.stock_quantity else "insufficient_stock"


def _image(variant) -> dict | None:
    images = list(variant.images.all())  # prefetched: active images only
    if not images:
        return None
    best = min(images, key=lambda i: (not i.is_primary, i.position, i.id))
    return {"url": best.url, "alt_text": best.alt_text, "width": best.width, "height": best.height}


def build_cart(user) -> dict:
    """Authoritative cart view. Constant query count: cart + items(joined) + images."""
    cart = Cart.objects.filter(user=user).first()
    items = []
    if cart is not None:
        items = list(
            CartItem.objects.filter(cart=cart)
            .select_related(
                "variant_size__size", "variant_size__variant__product__category"
            )
            .prefetch_related(
                Prefetch(
                    "variant_size__variant__images",
                    queryset=VariantImage.objects.filter(is_active=True),
                )
            )
        )
    lines = []
    total = Decimal("0")
    total_quantity = 0
    has_problem = False
    for item in items:
        vs = item.variant_size
        variant = vs.variant
        product = variant.product
        availability = _availability(item)
        unit_price = product.current_price
        subtotal = unit_price * item.quantity
        if availability != "unavailable":
            total += subtotal
            total_quantity += item.quantity
        if availability != "available":
            has_problem = True
        lines.append(
            {
                "id": item.id,
                "quantity": item.quantity,
                "availability": availability,
                "unit_price": unit_price,
                "subtotal": subtotal,
                "product": {"id": product.id, "name": product.name, "slug": product.slug},
                "color": {"name": variant.name, "slug": variant.slug, "hex_color": variant.hex_color},
                "variant_size": {"id": vs.id, "sku": vs.sku, "size": vs.size.code, "label": vs.size.label},
                "image": _image(variant),
            }
        )
    return {
        "items": lines,
        "item_count": len(lines),
        "total_quantity": total_quantity,
        "total": total,
        "has_issues": has_problem,
    }
