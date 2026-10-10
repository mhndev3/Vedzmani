"""Inventory audit trail: one `InventoryAdjustment` row per authorized stock change.

`catalog.VariantSize.stock_quantity` stays the single source of truth for the *current* quantity.
Adjustments are the history of changes made through `services.adjust_stock` (the supported way for staff
to change stock). Order checkout still decrements stock itself in `orders.services.create_order`; those
decrements are recorded by the order and its items, not by an adjustment.

History is append-only: the admin offers no change/delete, and both references are PROTECT so neither the
stock item nor the staff user can be deleted out from under their history.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

REASON_MAX_LENGTH = 255


class InventoryAdjustment(models.Model):
    variant_size = models.ForeignKey(
        "catalog.VariantSize", on_delete=models.PROTECT, related_name="inventory_adjustments"
    )
    quantity_change = models.IntegerField()  # signed: +N adds stock, -N removes stock; never 0
    stock_after = models.PositiveIntegerField()  # VariantSize.stock_quantity right after this change
    reason = models.CharField(max_length=REASON_MAX_LENGTH)
    # Null only for non-user (system/script) adjustments; the admin always records the staff user.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_adjustments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=~Q(quantity_change=0), name="inventory_adjustment_change_nonzero"),
        ]
        indexes = [
            # history of one stock item, newest first
            models.Index(fields=["variant_size", "-created_at"], name="invadj_variant_created_idx"),
        ]

    def __str__(self) -> str:
        return f"adjustment:{self.pk}"
