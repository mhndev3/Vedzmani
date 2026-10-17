"""Order administration: strictly read-only inspection (see backend/ADMIN.md).

* No add, change or delete for anyone, superusers included. `has_*_permission` return False, which makes Django itself
  answer 403 to direct add/change-POST/delete URLs; `save_model`, `delete_model`, `delete_queryset`, `save_formset`
  and `save_related` additionally raise, so no code path can persist through this admin. No admin actions exist.
* "View" means holding the model's *view* permission only. Django's default also treats `change_*` as view; that is
  switched off so a stray change grant never opens the order pages.
* PII (full phone, recipient name, province, city, address, postal code) is shown only to users holding
  `orders.view_order_pii` (permissions.py). Everyone else gets the masked phone and a notice. PII is also kept out of
  search, filters (query string), sorting and related-object columns for users without the permission. Hiding a form
  field alone would not do that.
* Django's default `lookup_allowed` accepts any field lookup on the model itself and any lookup across a single
  relation (`?customer_phone__startswith=...`, `?user__phone__startswith=...`, `?order__customer_phone__...`). That
  is a phone-number oracle for anyone who may view the list. `lookup_allowed` is therefore a whitelist.
"""

from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.constants import LOOKUP_SEP

from apps.accounts.phone import InvalidPhoneNumber, normalize_phone

from .models import Order, OrderItem
from .permissions import ORDER_PII_FIELDS, has_order_pii_permission, mask_phone

# Longest digit string that still fits a bigint primary key (avoids a DB error on absurd search input).
_MAX_ID_DIGITS = 18


class _ReadOnlyPermissions:
    """Shared by ModelAdmins and inlines: view needs only the model's own `view_*` permission; nothing mutates."""

    def has_view_permission(self, request, obj=None):
        opts = self.opts
        return bool(request.user.is_active and request.user.has_perm(f"{opts.app_label}.view_{opts.model_name}"))

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class _ReadOnlyModelAdmin(_ReadOnlyPermissions, admin.ModelAdmin):
    actions = None  # no bulk actions at all (delete_selected would be removed by the permissions anyway)
    list_editable = ()
    # First segment of every query-string lookup that is allowed. Everything else is a 400.
    safe_lookup_fields: frozenset = frozenset()

    def get_actions(self, request):
        return {}

    def to_field_allowed(self, request, to_field):
        # `?_popup=1&_to_field=customer_phone` would make a popup changelist print that column as the row value.
        # Only the primary key may ever be referenced this way.
        return to_field == "id" and super().to_field_allowed(request, to_field)

    def lookup_allowed(self, lookup, value, request=None):
        if lookup.split(LOOKUP_SEP)[0] not in self.safe_lookup_fields:
            return False
        return super().lookup_allowed(lookup, value, request)

    # Defence in depth: even if a permission check were ever loosened, nothing here can write.
    def save_model(self, request, obj, form, change):
        raise PermissionDenied

    def delete_model(self, request, obj):
        raise PermissionDenied

    def delete_queryset(self, request, queryset):
        raise PermissionDenied

    def save_formset(self, request, form, formset, change):
        raise PermissionDenied

    def save_related(self, request, form, formsets, change):
        raise PermissionDenied


class OrderItemInline(_ReadOnlyPermissions, admin.TabularInline):
    """Items of one order. Snapshot columns only: no join, no parent-order data, no link to catalog objects."""

    model = OrderItem
    extra = 0
    can_delete = False
    show_change_link = False
    fields = ("sku", "product_name", "color_name", "size_label", "unit_price", "quantity", "subtotal")
    readonly_fields = fields


@admin.register(Order)
class OrderAdmin(_ReadOnlyModelAdmin):
    list_display = ("id", "created_at", "masked_phone", "status", "payment_status", "total", "item_count")
    list_filter = ("status", "payment_status", "created_at")
    ordering = ("-created_at", "-id")
    # Baseline shown in the UI; get_search_fields() adds the PII columns for users who hold the permission.
    search_fields = ("items__sku", "items__product_name")
    inlines = [OrderItemInline]
    safe_lookup_fields = frozenset({"id", "status", "payment_status", "total", "created_at", "updated_at"})

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_item_count=Count("items"))

    # --- detail layout: PII only behind the dedicated permission ------------------------------
    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (
                None,
                {
                    "fields": (
                        "id", "created_at", "updated_at", "status", "payment_status", "total",
                        "masked_phone", "customer_account",
                    )
                },
            )
        ]
        if has_order_pii_permission(request.user):
            fieldsets.append(("Customer and delivery details (PII)", {"fields": ORDER_PII_FIELDS}))
        else:
            fieldsets.append(("Customer and delivery details", {"fields": ("pii_notice",)}))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        return flatten_fieldsets(self.get_fieldsets(request, obj))

    # --- search: PII columns only for holders of the permission --------------------------------
    def get_search_fields(self, request):
        fields = ["items__sku", "items__product_name"]
        if has_order_pii_permission(request.user):
            fields += ["customer_phone", "recipient_name"]
        return fields

    def get_search_results(self, request, queryset, search_term):
        term = (search_term or "").strip()
        if not term:
            return queryset, False
        condition = Q()
        for field in self.get_search_fields(request):
            condition |= Q(**{f"{field}__icontains": term})
        if term.isascii() and term.isdecimal() and len(term) <= _MAX_ID_DIGITS:
            condition |= Q(pk=int(term))  # order id (an integer column: never fed to a text lookup)
        if has_order_pii_permission(request.user):
            try:  # staff type 0912... / +98912...; the column stores the canonical form
                condition |= Q(customer_phone=normalize_phone(term))
            except InvalidPhoneNumber:
                pass
        # A subquery on a fresh queryset: the item join can neither duplicate rows nor distort the item count.
        matching = Order.objects.filter(condition).values("pk")
        return queryset.filter(pk__in=matching), False

    # --- columns ------------------------------------------------------------------------------
    # No `ordering=` on the phone column on purpose: sorting by it would reveal the order of the hidden digits.
    @admin.display(description="Customer phone")
    def masked_phone(self, obj):
        return mask_phone(obj.customer_phone)

    @admin.display(description="Account")
    def customer_account(self, obj):
        return f"#{obj.user_id}"  # id only: no link to the user admin and no account phone

    @admin.display(description="Items", ordering="_item_count")
    def item_count(self, obj):
        return obj._item_count

    @admin.display(description="Details")
    def pii_notice(self, obj):
        return "Hidden. Viewing the full phone number and delivery details needs the 'view order PII' permission."


@admin.register(OrderItem)
class OrderItemAdmin(_ReadOnlyModelAdmin):
    # The parent order is shown as a plain id only: no phone, no delivery data, no relation lookups.
    list_display = (
        "id", "order_ref", "sku", "product_name", "color_name", "size_label", "quantity", "unit_price", "subtotal",
    )
    search_fields = ("sku", "product_name")
    ordering = ("-order_id", "id")
    fields = list_display
    readonly_fields = fields
    safe_lookup_fields = frozenset(
        {"id", "sku", "product_name", "color_name", "size_label", "quantity", "unit_price", "subtotal"}
    )

    @admin.display(description="Order", ordering="order_id")
    def order_ref(self, obj):
        return f"#{obj.order_id}"
