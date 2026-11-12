"""Orders: an immutable record of what a user bought, created from their cart.

PostgreSQL is the source of truth. An order *snapshots* everything it needs (product/color/size names,
SKU, unit price, customer phone) so later catalog or user edits can never rewrite history. Order items keep
a PROTECT reference to the purchased `VariantSize` (for the future inventory/restock work) and PROTECT the
user, so neither can be deleted out from under an order.

Delivery details (recipient name, province, city, address, postal code) are snapshotted on the order at checkout
(Agent 11). The delivery phone is NOT stored separately: it is `customer_phone`, the account phone at order time.
Orders created before delivery details existed keep blank values for these columns (see ORDERS.md).

`payment_status` is server-owned; only a verified provider callback can move it to `paid`. Shipping is configured separately before payments can be enabled. All monetary values use Iranian Toman.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q


class Order(models.Model):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    STATUS_CHOICES = [(PENDING, "Pending"), (CONFIRMED, "Confirmed")]

    UNPAID = "unpaid"
    PAID = "paid"
    FAILED = "failed"
    PAYMENT_STATUS_CHOICES = [(UNPAID, "Unpaid"), (PAID, "Paid"), (FAILED, "Failed")]

    # The only delivery fields a client may supply at checkout (the API serializer and the service must agree).
    DELIVERY_FIELDS = ("recipient_name", "province", "city", "address", "postal_code")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=UNPAID)
    customer_phone = models.CharField(max_length=16)  # snapshot of User.phone at order time
    # Delivery snapshot (Iran). Defaults are "" so orders that predate these columns stay valid (blank, not NULL).
    recipient_name = models.CharField(max_length=120, default="")
    province = models.CharField(max_length=60, default="")
    city = models.CharField(max_length=60, default="")
    address = models.CharField(max_length=255, default="")
    postal_code = models.CharField(max_length=10, default="")  # exactly 10 ASCII digits for new orders
    # Whole-unit Decimal like the catalog/cart; sum of the item subtotals, computed on the server.
    # Shipping is NOT included (no shipping policy exists yet), so this is not a final delivered price.
    total = models.DecimalField(max_digits=18, decimal_places=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(total__gt=0), name="order_total_positive"),
        ]
        indexes = [models.Index(fields=["user", "-created_at"], name="order_user_created_idx")]

    def __str__(self) -> str:
        return f"order:{self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant_size = models.ForeignKey("catalog.VariantSize", on_delete=models.PROTECT, related_name="order_items")
    # --- snapshot: never read from the live catalog after creation ---
    product_name = models.CharField(max_length=200)
    color_name = models.CharField(max_length=60)
    size_label = models.CharField(max_length=40)
    sku = models.CharField(max_length=64)
    unit_price = models.DecimalField(max_digits=14, decimal_places=0)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=18, decimal_places=0)  # unit_price * quantity

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "variant_size"], name="orderitem_unique_order_variantsize"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="orderitem_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gt=0), name="orderitem_unit_price_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.order_id}:{self.sku}x{self.quantity}"


class SepPaymentAttempt(models.Model):
    """Server-owned SEP transaction attempt. Never stores card data or provider credentials."""
    INITIATING = "initiating"
    PENDING = "pending"
    PAID = "paid"
    OUT_OF_STOCK = "out_of_stock"
    FAILED = "failed"
    REVERSED = "reversed"
    STATUS_CHOICES = [
        (INITIATING, "Initiating"), (PENDING, "Pending"), (PAID, "Paid"),
        (OUT_OF_STOCK, "Out of stock"), (FAILED, "Failed"), (REVERSED, "Reversed"),
    ]
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="sep_payment_attempts")
    res_num = models.CharField(max_length=40, unique=True)
    token = models.CharField(max_length=100, blank=True, default="")
    ref_num = models.CharField(max_length=80, unique=True, null=True, blank=True)
    shipping_amount_toman = models.PositiveBigIntegerField()
    amount_rial = models.PositiveBigIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=INITIATING)
    provider_result_code = models.IntegerField(null=True, blank=True)
    provider_rrn = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["order", "-created_at"], name="sep_pay_order_created_idx")]

    def __str__(self) -> str:
        return f"sep:{self.res_num}:{self.status}"

