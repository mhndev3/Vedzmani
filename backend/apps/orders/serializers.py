from rest_framework import serializers

# Output only. Checkout takes NO client input: the owner, items, prices and total all come from the server.
_MONEY = dict(max_digits=18, decimal_places=0, read_only=True)


class OrderItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    variant_size_id = serializers.IntegerField()
    product_name = serializers.CharField()
    color_name = serializers.CharField()
    size_label = serializers.CharField()
    sku = serializers.CharField()
    unit_price = serializers.DecimalField(**_MONEY)
    quantity = serializers.IntegerField()
    subtotal = serializers.DecimalField(**_MONEY)


class OrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    customer_phone = serializers.CharField()
    total = serializers.DecimalField(**_MONEY)
    created_at = serializers.DateTimeField()
    items = OrderItemSerializer(many=True)
