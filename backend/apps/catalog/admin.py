"""Catalog administration (Django-native admin; permissions are the stock model permissions).

Editing flow: Product (+ color variants inline) -> ColorVariant page (+ sizes/stock and images inlines).
Django has no nested inlines, so sizes and images live on the ColorVariant page on purpose.

`stock_quantity` is editable here because no inventory module exists yet to set initial stock.
Once orders exist, stock changes must go through the inventory module (see CATALOG.md / handoff).
"""

from django import forms
from django.contrib import admin
from django.db.models import Count
from django.forms.models import BaseInlineFormSet

from .models import Category, Collection, ColorVariant, Product, Size, VariantImage, VariantSize


# --- inlines ---------------------------------------------------------------
class ColorVariantInline(admin.TabularInline):
    model = ColorVariant
    extra = 0
    fields = ("name", "slug", "hex_color", "position", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    show_change_link = True  # sizes / images are edited on the variant page


class VariantSizeInline(admin.TabularInline):
    model = VariantSize
    extra = 0
    fields = ("size", "sku", "stock_quantity", "is_active")


class VariantImageInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        primaries = sum(
            1
            for form in self.forms
            if getattr(form, "cleaned_data", None)
            and not form.cleaned_data.get("DELETE")
            and form.cleaned_data.get("is_primary")
        )
        if primaries > 1:
            raise forms.ValidationError("Only one image per color variant can be primary.")

    def save_existing_objects(self, commit=True):
        # Moving the primary flag to a row that is saved BEFORE the old primary is cleared would trip the
        # one-primary-per-variant DB constraint (inline forms skip that check). Clear demoted/deleted
        # primaries first; this runs inside the admin's change-view transaction.
        if commit:
            cleared = [
                form.instance.pk
                for form in self.initial_forms
                if form.initial.get("is_primary")
                and (form.cleaned_data.get("DELETE") or not form.cleaned_data.get("is_primary"))
            ]
            if cleared:
                VariantImage.objects.filter(pk__in=cleared).update(is_primary=False)
        return super().save_existing_objects(commit)


class VariantImageInline(admin.TabularInline):
    model = VariantImage
    formset = VariantImageInlineFormSet
    extra = 0
    fields = (
        "storage_key", "alt_text", "position", "is_primary", "is_active",
        "width", "height", "content_type", "file_size", "url",
    )
    readonly_fields = ("url",)


# --- simple vocabularies -----------------------------------------------------
class _PositionedAdmin(admin.ModelAdmin):
    list_editable = ("is_active", "position")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    ordering = ("position", "id")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Category)
class CategoryAdmin(_PositionedAdmin):
    list_display = ("name", "slug", "is_active", "position", "product_count")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_product_count=Count("products", distinct=True))

    @admin.display(description="Products", ordering="_product_count")
    def product_count(self, obj):
        return obj._product_count


@admin.register(Collection)
class CollectionAdmin(_PositionedAdmin):
    list_display = ("name", "slug", "is_active", "position", "product_count")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_product_count=Count("products", distinct=True))

    @admin.display(description="Products", ordering="_product_count")
    def product_count(self, obj):
        return obj._product_count


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "position")
    search_fields = ("code", "label")
    ordering = ("position", "id")


# --- product ------------------------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "category", "is_active", "price", "sale_price", "current_price", "variant_count", "updated_at",
    )
    list_editable = ("is_active",)
    list_filter = ("is_active", "category", "collections")
    list_select_related = ("category",)
    search_fields = ("name", "slug", "color_variants__sizes__sku")
    ordering = ("-created_at", "-id")
    autocomplete_fields = ("category",)
    filter_horizontal = ("collections",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("current_price", "created_at", "updated_at")
    inlines = [ColorVariantInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "category", "collections", "description")}),
        ("Pricing", {"fields": ("price", "sale_price", "current_price")}),
        ("Publication", {"fields": ("is_active",)}),
        ("Timestamps", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_variant_count=Count("color_variants", distinct=True))

    @admin.display(description="Colors", ordering="_variant_count")
    def variant_count(self, obj):
        return obj._variant_count


@admin.register(ColorVariant)
class ColorVariantAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "slug", "is_active", "position", "size_count", "image_count")
    list_filter = ("is_active", "product__category")
    list_select_related = ("product",)
    search_fields = ("name", "slug", "product__name", "sizes__sku")
    ordering = ("product__name", "position", "id")
    autocomplete_fields = ("product",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = [VariantSizeInline, VariantImageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _size_count=Count("sizes", distinct=True), _image_count=Count("images", distinct=True)
        )

    @admin.display(description="Sizes", ordering="_size_count")
    def size_count(self, obj):
        return obj._size_count

    @admin.display(description="Images", ordering="_image_count")
    def image_count(self, obj):
        return obj._image_count


class _VariantColumnsMixin:
    @admin.display(description="Product", ordering="variant__product__name")
    def product(self, obj):
        return obj.variant.product.name

    @admin.display(description="Color", ordering="variant__name")
    def color(self, obj):
        return obj.variant.name


@admin.register(VariantSize)
class VariantSizeAdmin(_VariantColumnsMixin, admin.ModelAdmin):
    list_display = ("sku", "product", "color", "size", "stock_quantity", "is_active")
    list_filter = ("is_active", "size")
    list_select_related = ("variant__product", "size")
    search_fields = ("sku", "variant__product__name", "variant__name")
    ordering = ("variant__product__name", "variant__position", "size__position")
    autocomplete_fields = ("variant",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(VariantImage)
class VariantImageAdmin(_VariantColumnsMixin, admin.ModelAdmin):
    list_display = ("storage_key", "product", "color", "position", "is_primary", "is_active", "width", "height")
    list_filter = ("is_active", "is_primary")
    list_select_related = ("variant__product",)
    search_fields = ("storage_key", "alt_text", "variant__product__name", "variant__name")
    ordering = ("variant__product__name", "variant__position", "position")
    autocomplete_fields = ("variant",)
    readonly_fields = ("url", "created_at", "updated_at")
