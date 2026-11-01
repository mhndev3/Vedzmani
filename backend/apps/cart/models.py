"""Shopping cart: a per-user, non-reserving list of purchasable variants."""
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


class GuestCartMerge(models.Model):
    """Idempotency receipt for a guest-cart transfer into an authenticated account."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="guest_cart_merges")
    token = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "token"], name="guestcartmerge_user_token_uniq"),
        ]
        indexes = [models.Index(fields=["user", "-created_at"], name="guestmerge_user_created_idx")]

    def __str__(self) -> str:
        return f"guest-cart-merge:{self.user_id}:{self.token}"
