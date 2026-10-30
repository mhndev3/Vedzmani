"""Catalog administration (Django-native admin; permissions are the stock model permissions).

Editing flow: Product (+ color variants inline) -> ColorVariant page (+ sizes/stock and images inlines).
Django has no nested inlines, so sizes and images live on the ColorVariant page on purpose.

`stock_quantity` is READ-ONLY everywhere in this admin (size inline and VariantSize page): a new size starts
at 0 and stock only changes through inventory adjustments (`apps.inventory`, see INVENTORY.md), which lock the
row and write an audit record. Direct edits here could overwrite a concurrent order decrement.
"""

from urllib.parse import urlencode

from django import forms
from django.contrib import admin
from django.db.models import Count
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.utils.html import format_html

from .models import Category, Collection, ColorVariant, Product, ProductSizeDescription, ProductSizeMeasurement, Size, VariantImage, VariantSize, VariantSizeDescription


class ProductAdminForm(forms.ModelForm):
    product_code = forms.CharField(label="کد محصول", max_length=40, required=True)

    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["price"].label = "قیمت (تومان)"
        self.fields["sale_price"].label = "قیمت با تخفیف (تومان)"
        self.fields["price"].help_text = "تمام قیمت‌های محصولات به تومان ثبت می‌شوند."
        self.fields["sale_price"].help_text = "در صورت ثبت، مبلغ تخفیف‌خورده نیز به تومان است."




# --- inlines ---------------------------------------------------------------
class ProductSizeMeasurementInline(admin.TabularInline):
    model = ProductSizeMeasurement
    extra = 0
    autocomplete_fields = ("size",)
    fields = ("size", "name", "value", "unit", "position")


class ProductSizeDescriptionInline(admin.TabularInline):
    model = ProductSizeDescription
    extra = 0
    autocomplete_fields = ("size",)
    fields = ("size", "description")


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
    readonly_fields = ("stock_quantity",)  # changed only via inventory adjustments


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
    form = ProductAdminForm
    list_display = (
        "product_code", "name", "category", "is_active",
        "base_price_toman", "sale_price_toman", "current_price_toman",
        "variant_count", "updated_at",
    )
    list_editable = ("is_active",)
    list_filter = ("is_active", "category", "collections")
    list_select_related = ("category",)
    search_fields = ("product_code", "name", "slug", "color_variants__sizes__sku")
    ordering = ("-created_at", "-id")
    autocomplete_fields = ("category",)
    filter_horizontal = ("collections",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("current_price", "created_at", "updated_at")
    inlines = [ProductSizeMeasurementInline, ProductSizeDescriptionInline, ColorVariantInline]
    fieldsets = (
        (None, {"fields": ("product_code", "name", "slug", "category", "collections", "description")}),
        ("Pricing", {"fields": ("price", "sale_price", "current_price")}),
        ("Publication", {"fields": ("is_active",)}),
        ("Timestamps", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="قیمت پایه (تومان)", ordering="price")
    def base_price_toman(self, obj):
        return obj.price

    @admin.display(description="قیمت با تخفیف (تومان)", ordering="sale_price")
    def sale_price_toman(self, obj):
        return obj.sale_price if obj.sale_price is not None else "—"

    @admin.display(description="قیمت فعلی (تومان)", ordering="sale_price")
    def current_price_toman(self, obj):
        return obj.current_price

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
    # stock is changed only through inventory adjustments (apps.inventory), never by editing the column here
    readonly_fields = ("stock_quantity", "created_at", "updated_at")
    inlines = [VariantSizeDescriptionInline]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is not None and request.user.has_perm("inventory.add_inventoryadjustment"):
            fields = (*fields, "adjust_stock_link")
        return fields

    @admin.display(description="Stock actions")
    def adjust_stock_link(self, obj):
        url = reverse("admin:inventory_inventoryadjustment_add") + "?" + urlencode({"variant_size": obj.pk})
        return format_html('<a href="{}">Adjust stock (add or remove units)</a>', url)


class VariantSizeDescriptionInline(admin.TabularInline):
    model = VariantSizeDescription
    extra = 0
    max_num = 1
    fields = ("description",)


@admin.register(VariantImage)
class VariantImageAdmin(_VariantColumnsMixin, admin.ModelAdmin):
    list_display = ("storage_key", "product", "color", "position", "is_primary", "is_active", "width", "height")
    list_filter = ("is_active", "is_primary")
    list_select_related = ("variant__product",)
    search_fields = ("storage_key", "alt_text", "variant__product__name", "variant__name")
    ordering = ("variant__product__name", "variant__position", "position")
    autocomplete_fields = ("variant",)
    readonly_fields = ("url", "created_at", "updated_at")
