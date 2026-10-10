"""Cart administration: inspection only.

Carts belong to customers and are priced from the catalog at request time, so staff can look but not
create/edit (no silent ownership, quantity or price changes). Delete permission is left to Django's
model permissions on purpose: overriding it would also block deleting a *user* who owns a cart.
The cart is not an inventory reservation; nothing here touches stock.
"""

from django.contrib import admin
from django.db.models import Count

from .models import Cart, CartItem


def mask_phone(phone: str) -> str:
    """+989123456789 -> +9891****789 (enough to tell customers apart, not to contact them)."""
    return f"{phone[:5]}****{phone[-3:]}" if len(phone) > 8 else "****"


class _ReadOnlyMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class CartItemInline(_ReadOnlyMixin, admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("sku", "product", "color", "size", "quantity", "created_at")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("variant_size__variant__product", "variant_size__size")

    @admin.display(description="SKU")
    def sku(self, obj):
        return obj.variant_size.sku

    @admin.display(description="Product")
    def product(self, obj):
        return obj.variant_size.variant.product.name

    @admin.display(description="Color")
    def color(self, obj):
        return obj.variant_size.variant.name

    @admin.display(description="Size")
    def size(self, obj):
        return obj.variant_size.size.label


@admin.register(Cart)
class CartAdmin(_ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "owner", "item_count", "created_at", "updated_at")
    list_select_related = ("user",)
    search_fields = ("user__phone",)
    ordering = ("-updated_at", "-id")
    fields = ("id", "owner", "created_at", "updated_at")
    readonly_fields = fields
    inlines = [CartItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_item_count=Count("items", distinct=True))

    @admin.display(description="Owner")
    def owner(self, obj):
        return f"#{obj.user_id} {mask_phone(obj.user.phone)}"

    @admin.display(description="Lines", ordering="_item_count")
    def item_count(self, obj):
        return obj._item_count


@admin.register(CartItem)
class CartItemAdmin(_ReadOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "owner", "sku", "product", "quantity", "updated_at")
    list_select_related = ("cart__user", "variant_size__variant__product")
    search_fields = ("variant_size__sku", "variant_size__variant__product__name", "cart__user__phone")
    ordering = ("-updated_at", "-id")
    fields = ("id", "owner", "sku", "product", "quantity", "created_at", "updated_at")
    readonly_fields = fields

    @admin.display(description="Owner")
    def owner(self, obj):
        return f"#{obj.cart.user_id} {mask_phone(obj.cart.user.phone)}"

    @admin.display(description="SKU")
    def sku(self, obj):
        return obj.variant_size.sku

    @admin.display(description="Product")
    def product(self, obj):
        return obj.variant_size.variant.product.name
