"""Staff-only serializers for the custom catalog workspace API.

All write paths deliberately expose model fields rather than accepting arbitrary nested object graphs.
Related records are managed through their own permission-checked endpoints. Stock and image storage keys are
never writable through these serializers.
"""
from django.db import transaction
from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Collection,
    ColorVariant,
    Product,
    ProductSizeMeasurement,
    Size,
    VariantImage,
    VariantSize,
    VariantSizeMeasurement,
)
from apps.inventory.models import InventoryAdjustment
from apps.inventory.services import adjust_stock


class CategoryAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "is_active", "position", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CollectionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = ["id", "name", "slug", "is_active", "position", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SizeAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ["id", "code", "label", "position"]
        read_only_fields = ["id"]


class VariantSizeSummarySerializer(serializers.ModelSerializer):
    size_code = serializers.CharField(source="size.code", read_only=True)
    size_label = serializers.CharField(source="size.label", read_only=True)

    class Meta:
        model = VariantSize
        fields = ["id", "size", "size_code", "size_label", "sku", "stock_quantity", "is_active"]
        read_only_fields = fields


class ColorVariantSummarySerializer(serializers.ModelSerializer):
    sizes = VariantSizeSummarySerializer(many=True, read_only=True)

    class Meta:
        model = ColorVariant
        fields = ["id", "name", "slug", "product_code", "hex_color", "is_active", "position", "sizes"]
        read_only_fields = fields


class ProductAdminSerializer(serializers.ModelSerializer):
    colors = ColorVariantSummarySerializer(source="color_variants", many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "product_code", "name", "slug", "description", "price", "sale_price",
            "category", "collections", "is_active", "colors", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "colors"]


class ColorVariantAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorVariant
        fields = [
            "id", "product", "name", "slug", "product_code", "hex_color",
            "is_active", "position", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "product_code", "created_at", "updated_at"]


class VariantSizeAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantSize
        fields = ["id", "variant", "size", "sku", "stock_quantity", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "stock_quantity", "created_at", "updated_at"]


class ProductSizeMeasurementAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSizeMeasurement
        fields = ["id", "product", "size", "name", "value", "unit", "position"]
        read_only_fields = ["id"]


class VariantSizeMeasurementAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantSizeMeasurement
        fields = ["id", "variant_size", "name", "value", "unit", "position"]
        read_only_fields = ["id"]


class VariantImageReadSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = VariantImage
        fields = [
            "id", "variant", "url", "alt_text", "position", "is_primary",
            "width", "height", "content_type", "file_size", "is_active",
        ]
        read_only_fields = fields


class InventoryAdjustmentAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryAdjustment
        fields = [
            "id", "variant_size", "quantity_change", "stock_after",
            "reason", "created_by", "created_at",
        ]
        read_only_fields = ["id", "stock_after", "created_by", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        return adjust_stock(
            variant_size_id=validated_data["variant_size"].pk,
            quantity_change=validated_data["quantity_change"],
            reason=validated_data["reason"],
            created_by=request.user,
        )
