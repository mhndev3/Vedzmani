import unicodedata

from rest_framework import serializers

from .postal_code import InvalidPostalCode, normalize_postal_code

# Output-only money: owner, items, prices and total always come from the server.
_MONEY = dict(max_digits=18, decimal_places=0, read_only=True)


class _TextField(serializers.CharField):
    """Single-line text for checkout input.

    Stricter than DRF's CharField: JSON numbers/bools are NOT coerced to strings, and control characters
    (newlines, tabs, NUL, ...) are rejected. Zero-width non-joiner and other format characters stay allowed
    because Persian text needs them. Error messages never contain the submitted value.
    """

    default_error_messages = {
        "not_a_string": "Must be a string.",
        "control_characters": "Control characters are not allowed.",
    }

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("not_a_string")
        # Check the RAW string: DRF's CharField trims whitespace (str.strip also removes a leading/trailing \n or
        # \t), so checking afterwards would silently accept them. Spaces are not control characters and are still
        # trimmed; a value that is only whitespace is rejected as `blank` before this method runs.
        if any(unicodedata.category(char) == "Cc" for char in data):
            self.fail("control_characters")
        return super().to_internal_value(data)


class PostalCodeField(_TextField):
    default_error_messages = {"invalid_postal_code": "Enter a valid 10-digit postal code."}

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_postal_code(value)
        except InvalidPostalCode:
            self.fail("invalid_postal_code")


class CheckoutSerializer(serializers.Serializer):
    """The ONLY client input to order creation: Iranian delivery details.

    Unknown keys (user, total, status, payment_status, phone, ...) are ignored by DRF and are never read:
    `validated_data` contains exactly `Order.DELIVERY_FIELDS`. The delivery phone is not accepted; it is the
    authenticated account's phone (snapshotted as `Order.customer_phone`).
    """

    recipient_name = _TextField(max_length=120)
    province = _TextField(max_length=60)
    city = _TextField(max_length=60)
    address = _TextField(max_length=255)
    postal_code = PostalCodeField()


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
    """Output only. Delivery fields are "" for orders created before delivery details existed."""

    id = serializers.IntegerField()
    status = serializers.CharField()
    payment_status = serializers.CharField()
    customer_phone = serializers.CharField()
    recipient_name = serializers.CharField()
    province = serializers.CharField()
    city = serializers.CharField()
    address = serializers.CharField()
    postal_code = serializers.CharField()
    total = serializers.DecimalField(**_MONEY)  # sum of line subtotals; excludes shipping (no shipping policy yet)
    created_at = serializers.DateTimeField()
    items = OrderItemSerializer(many=True)
