"""Catalog listing query builders: parameter validation, filtering, search and sorting.

The compatibility product endpoint pages Product rows without join fan-out. The storefront
variant endpoint pages ColorVariant rows, intentionally returning one card per active color.
Both builders keep filters and ordering in SQL; related collections and purchasable sizes use
Exists subqueries so each endpoint has an accurate count and no accidental row multiplication.
"""

import re

from django.db.models import DecimalField, Exists, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from rest_framework import serializers

from .models import ColorVariant, Product, VariantImage, VariantSize

MAX_SEARCH_TERMS = 5
MAX_LIST_VALUES = 10
SLUG_RE = re.compile(r"^[-a-zA-Z0-9_]+$")

# Explicit whitelist; every ordering ends in a unique tiebreaker so pagination is stable.
SORT_OPTIONS = {
    "newest": ("-created_at", "-id"),
    "price_asc": ("effective_price", "id"),
    "price_desc": ("-effective_price", "-id"),
    "name_asc": ("name", "id"),
    "name_desc": ("-name", "-id"),
}
DEFAULT_SORT = "newest"


def _slug_list(value: str) -> list[str]:
    """'a,b' -> ['a', 'b'] with validation; empty string -> []."""
    items = [v.strip() for v in value.split(",") if v.strip()]
    if len(items) > MAX_LIST_VALUES:
        raise serializers.ValidationError(f"At most {MAX_LIST_VALUES} values are allowed.")
    if any(not SLUG_RE.match(v) for v in items):
        raise serializers.ValidationError("Values may only contain letters, digits, '-' and '_'.")
    return items


class CatalogQuerySerializer(serializers.Serializer):
    """Validates listing query params. Use with `partial=True` so absent params stay absent."""

    search = serializers.CharField(required=False, allow_blank=True, max_length=100)
    category = serializers.CharField(required=False, allow_blank=True, max_length=400)
    collection = serializers.CharField(required=False, allow_blank=True, max_length=400)
    color = serializers.CharField(required=False, allow_blank=True, max_length=400)
    size = serializers.CharField(required=False, allow_blank=True, max_length=400)
    min_price = serializers.IntegerField(required=False, min_value=0, max_value=10**14 - 1)
    max_price = serializers.IntegerField(required=False, min_value=0, max_value=10**14 - 1)
    in_stock = serializers.BooleanField(required=False)
    sort = serializers.ChoiceField(required=False, choices=list(SORT_OPTIONS))

    def validate_category(self, value):
        return _slug_list(value)

    validate_collection = validate_category
    validate_color = validate_category
    validate_size = validate_category

    def validate(self, attrs):
        low, high = attrs.get("min_price"), attrs.get("max_price")
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({"min_price": "min_price must not exceed max_price."})
        return attrs


def _search_q(term: str) -> Q:
    collection_match = Product.collections.through.objects.filter(
        product_id=OuterRef("pk"),
        collection__is_active=True,
        collection__name__icontains=term,
    )
    return (
        Q(name__icontains=term)
        | Q(product_code__icontains=term)
        | Q(slug__icontains=term)
        | Q(description__icontains=term)
        | Q(category__name__icontains=term)
        | Q(Exists(collection_match))
    )


def _representative_image(field: str) -> Subquery:
    """One image per product: first active variant (by position), its primary image first."""
    image = (
        VariantImage.objects.filter(variant__product=OuterRef("pk"), is_active=True, variant__is_active=True)
        .order_by("variant__position", "variant_id", "-is_primary", "position", "id")
        .values(field)[:1]
    )
    return Subquery(image)


def build_product_queryset(params: dict):
    """Public, active-only product queryset with filters, search, annotations and ordering applied."""
    qs = Product.objects.filter(is_active=True, category__is_active=True).select_related("category")

    purchasable = VariantSize.objects.filter(
        variant__product=OuterRef("pk"), is_active=True, variant__is_active=True
    )
    qs = qs.annotate(
        effective_price=Coalesce("sale_price", "price", output_field=DecimalField(max_digits=14, decimal_places=0)),
        in_stock=Exists(purchasable.filter(stock_quantity__gt=0)),
        image_key=_representative_image("storage_key"),
        image_thumbnail_key=_representative_image("thumbnail_storage_key"),
        image_alt=_representative_image("alt_text"),
        image_width=_representative_image("width"),
        image_height=_representative_image("height"),
    )

    for term in (params.get("search") or "").split()[:MAX_SEARCH_TERMS]:
        qs = qs.filter(_search_q(term))  # every term must match somewhere (AND), any field (OR)

    if params.get("category"):
        qs = qs.filter(category__slug__in=params["category"])

    if params.get("collection"):
        in_collection = Product.collections.through.objects.filter(
            product_id=OuterRef("pk"),
            collection__is_active=True,
            collection__slug__in=params["collection"],
        )
        qs = qs.filter(Exists(in_collection))

    # color / size / in_stock describe ONE purchasable unit: "black + M + in stock" must be
    # satisfied by a single VariantSize, not by different rows of the same product.
    unit = purchasable
    needs_unit = False
    if params.get("color"):
        unit, needs_unit = unit.filter(variant__slug__in=params["color"]), True
    if params.get("size"):
        unit, needs_unit = unit.filter(size__code__in=params["size"], stock_quantity__gt=0), True
    if params.get("in_stock"):
        unit, needs_unit = unit.filter(stock_quantity__gt=0), True
    if needs_unit:
        qs = qs.filter(Exists(unit))

    if params.get("min_price") is not None:
        qs = qs.filter(effective_price__gte=params["min_price"])
    if params.get("max_price") is not None:
        qs = qs.filter(effective_price__lte=params["max_price"])

    return qs.order_by(*SORT_OPTIONS[params.get("sort", DEFAULT_SORT)])


def active_colors_queryset():
    """Lightweight swatch data for product cards (no images, no sizes)."""
    return ColorVariant.objects.filter(is_active=True).only("id", "product_id", "name", "slug", "hex_color", "position")


def _variant_search_q(term: str) -> Q:
    collection_match = Product.collections.through.objects.filter(
        product_id=OuterRef("product_id"),
        collection__is_active=True,
        collection__name__icontains=term,
    )
    return (
        Q(product__name__icontains=term)
        | Q(name__icontains=term)
        | Q(slug__icontains=term)
        | Q(product__product_code__icontains=term)
        | Q(product__slug__icontains=term)
        | Q(product__description__icontains=term)
        | Q(product__category__name__icontains=term)
        | Q(Exists(collection_match))
    )


def _variant_image(field: str) -> Subquery:
    image = (
        VariantImage.objects.filter(variant=OuterRef("pk"), is_active=True)
        .order_by("-is_primary", "position", "id")
        .values(field)[:1]
    )
    return Subquery(image)


def build_variant_queryset(params: dict):
    """One storefront row per active color variant, with variant-owned media and stock."""
    qs = ColorVariant.objects.filter(
        is_active=True,
        product__is_active=True,
        product__category__is_active=True,
    ).select_related("product", "product__category")

    purchasable = VariantSize.objects.filter(variant=OuterRef("pk"), is_active=True)
    qs = qs.annotate(
        effective_price=Coalesce(
            "product__sale_price", "product__price",
            output_field=DecimalField(max_digits=14, decimal_places=0),
        ),
        in_stock=Exists(purchasable.filter(stock_quantity__gt=0)),
        image_key=_variant_image("storage_key"),
        image_thumbnail_key=_variant_image("thumbnail_storage_key"),
        image_alt=_variant_image("alt_text"),
        image_width=_variant_image("width"),
        image_height=_variant_image("height"),
    )

    for term in (params.get("search") or "").split()[:MAX_SEARCH_TERMS]:
        qs = qs.filter(_variant_search_q(term))

    if params.get("category"):
        qs = qs.filter(product__category__slug__in=params["category"])

    if params.get("collection"):
        in_collection = Product.collections.through.objects.filter(
            product_id=OuterRef("product_id"),
            collection__is_active=True,
            collection__slug__in=params["collection"],
        )
        qs = qs.filter(Exists(in_collection))

    if params.get("color"):
        qs = qs.filter(slug__in=params["color"])

    if params.get("size"):
        qs = qs.filter(Exists(purchasable.filter(size__code__in=params["size"], stock_quantity__gt=0)))

    if params.get("in_stock"):
        qs = qs.filter(Exists(purchasable.filter(stock_quantity__gt=0)))

    if params.get("min_price") is not None:
        qs = qs.filter(effective_price__gte=params["min_price"])
    if params.get("max_price") is not None:
        qs = qs.filter(effective_price__lte=params["max_price"])

    sort_options = {
        "newest": ("-product__created_at", "-product_id", "position", "id"),
        "price_asc": ("effective_price", "product_id", "position", "id"),
        "price_desc": ("-effective_price", "-product_id", "position", "id"),
        "name_asc": ("product__name", "product_id", "position", "id"),
        "name_desc": ("-product__name", "-product_id", "position", "id"),
    }
    return qs.order_by(*sort_options[params.get("sort", DEFAULT_SORT)])
