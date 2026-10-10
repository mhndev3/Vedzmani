"""Shopping cart: a per-user, *non-reserving* list of VariantSize + quantity.

PostgreSQL is the source of truth. A cart never changes `VariantSize.stock_quantity`;
stock is only validated when lines are added/edited and must be validated again by checkout.
Prices are NOT stored: they are read from the catalog at request time, so a cart can never
hold a stale or client-supplied price.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"cart:{self.user_id}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    # Deleting a purchasable unit from the catalog simply drops it from carts (carts are transient;
    # orders will snapshot their own data).
    variant_size = models.ForeignKey("catalog.VariantSize", on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant_size"], name="cartitem_unique_cart_variantsize"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="cartitem_quantity_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.cart_id}:{self.variant_size_id}x{self.quantity}"
