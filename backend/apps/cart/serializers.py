from rest_framework import serializers

from .services import MAX_BIGINT


class AddItemSerializer(serializers.Serializer):
    variant_size_id = serializers.IntegerField(min_value=1, max_value=MAX_BIGINT)
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class GuestCartMergeItemSerializer(serializers.Serializer):
    variant_size_id = serializers.IntegerField(min_value=1, max_value=MAX_BIGINT)
    quantity = serializers.IntegerField(min_value=1)


class GuestCartMergeSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    items = GuestCartMergeItemSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        if len(items) > settings.CART_MAX_LINES:
            raise serializers.ValidationError("Too many distinct cart lines.", code="cart_full")
        ids = [item["variant_size_id"] for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Duplicate variant sizes are not allowed.", code="duplicate_items")
        return items


# --- response (money is a whole-Toman Decimal rendered as a string, like the catalog) ---

_MONEY = dict(max_digits=18, decimal_places=0, read_only=True)


class _ProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class _ColorSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    hex_color = serializers.CharField()


class _VariantSizeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sku = serializers.CharField()
    size = serializers.CharField()
    label = serializers.CharField()


class _ImageSerializer(serializers.Serializer):
    url = serializers.CharField()
    thumbnail_url = serializers.CharField()
    alt_text = serializers.CharField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()


class CartItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    quantity = serializers.IntegerField()
    stock_quantity = serializers.IntegerField()
    availability = serializers.CharField()
    unit_price = serializers.DecimalField(**_MONEY)
    subtotal = serializers.DecimalField(**_MONEY)
    product = _ProductSerializer()
    color = _ColorSerializer()
    variant_size = _VariantSizeSerializer()
    image = _ImageSerializer(allow_null=True)


class CartSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    item_count = serializers.IntegerField()
    total_quantity = serializers.IntegerField()
    total = serializers.DecimalField(**_MONEY)
    has_issues = serializers.BooleanField()
