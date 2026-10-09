from django.conf import settings
from rest_framework import serializers

from .services import MAX_BIGINT


class AddItemSerializer(serializers.Serializer):
    variant_size_id = serializers.IntegerField(min_value=1, max_value=MAX_BIGINT)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_quantity(self, value):
        if value > settings.CART_MAX_ITEM_QUANTITY:
            raise serializers.ValidationError(
                f"At most {settings.CART_MAX_ITEM_QUANTITY} units per item.", code="max_quantity"
            )
        return value


class UpdateItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)

    validate_quantity = AddItemSerializer.validate_quantity


# --- response (money is a whole-unit Decimal rendered as a string, like the catalog) ---

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
    alt_text = serializers.CharField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()


class CartItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    quantity = serializers.IntegerField()
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
