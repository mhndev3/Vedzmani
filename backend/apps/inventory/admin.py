"""Inventory administration (Django-native admin; the stock per-model permissions apply).

* Create: staff with `inventory.add_inventoryadjustment` record a signed adjustment. The admin never saves the
  form's model instance itself; `save_model` calls `services.adjust_stock` (lock + validation + audit in one
  transaction), so this page cannot bypass the service. Staff also need `catalog.view_variantsize`
  (the stock item picker is an autocomplete over `VariantSize`).
* History: read-only for anyone with `inventory.view_inventoryadjustment`. There is no change and no delete, not even
  for superusers: the audit trail is append-only.
"""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from rest_framework.exceptions import APIException

from . import services
from .models import InventoryAdjustment

DETAIL_FIELDS = ("variant_size", "quantity_change", "stock_after", "reason", "created_by", "created_at")


class InventoryAdjustmentForm(forms.ModelForm):
    class Meta:
        model = InventoryAdjustment
        fields = ("variant_size", "quantity_change", "reason")
        help_texts = {"quantity_change": "Positive adds stock, negative removes it. Zero is not allowed."}

    def clean_quantity_change(self):
        value = self.cleaned_data["quantity_change"]
        if value == 0:
            raise forms.ValidationError("Enter a non-zero quantity (negative removes stock).")
        return value

    def clean_reason(self):
        reason = (self.cleaned_data["reason"] or "").strip()
        if not reason:
            raise forms.ValidationError("A reason is required.")
        return reason

    def clean(self):
        cleaned = super().clean()
        variant_size, change = cleaned.get("variant_size"), cleaned.get("quantity_change")
        # Friendly pre-check on an unlocked read; the service re-checks under the row lock.
        if variant_size is not None and change is not None and variant_size.stock_quantity + change < 0:
            raise forms.ValidationError(
                f"Cannot remove {-change}: only {variant_size.stock_quantity} in stock for {variant_size.sku}."
            )
        return cleaned


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    form = InventoryAdjustmentForm
    list_display = (
        "created_at", "sku", "product", "color", "size", "quantity_change", "stock_after", "reason", "created_by",
    )
    list_select_related = ("variant_size__variant__product", "variant_size__size", "created_by")
    search_fields = ("variant_size__sku", "variant_size__variant__product__name", "reason", "created_by__phone")
    ordering = ("-created_at", "-id")
    autocomplete_fields = ("variant_size",)

    # --- permissions: append-only history ---------------------------------------------------
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        return DETAIL_FIELDS if obj is not None else ("variant_size", "quantity_change", "reason")

    def get_readonly_fields(self, request, obj=None):
        return DETAIL_FIELDS if obj is not None else ()

    # --- create goes through the service ----------------------------------------------------
    def save_model(self, request, obj, form, change):
        if change:  # no change permission exists; never persist an edit of an audit row
            raise PermissionDenied
        try:
            saved = services.adjust_stock(
                variant_size_id=obj.variant_size_id,
                quantity_change=obj.quantity_change,
                reason=obj.reason,
                created_by=request.user,
            )
        except APIException as exc:  # e.g. someone else removed stock between validation and save
            obj._adjustment_failure = str(exc.detail)
            return
        for name in ("id", "reason", "stock_after", "created_by", "created_at"):
            setattr(obj, name, getattr(saved, name))
        obj._state.adding = False

    def log_addition(self, request, obj, message):
        if obj.pk is None:  # the service rejected it; nothing was recorded
            return None
        return super().log_addition(request, obj, message)

    def response_add(self, request, obj, post_url_continue=None):
        failure = getattr(obj, "_adjustment_failure", None)
        if failure:
            self.message_user(request, failure, messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())
        return super().response_add(request, obj, post_url_continue)

    # --- list columns -----------------------------------------------------------------------
    @admin.display(description="SKU", ordering="variant_size__sku")
    def sku(self, obj):
        return obj.variant_size.sku

    @admin.display(description="Product", ordering="variant_size__variant__product__name")
    def product(self, obj):
        return obj.variant_size.variant.product.name

    @admin.display(description="Color", ordering="variant_size__variant__name")
    def color(self, obj):
        return obj.variant_size.variant.name

    @admin.display(description="Size", ordering="variant_size__size__position")
    def size(self, obj):
        return obj.variant_size.size.label
