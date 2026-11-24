"""Staff-only serializers for the custom catalog workspace API.

All write paths deliberately expose model fields rather than accepting arbitrary nested object graphs.
Related records are managed through their own permission-checked endpoints. Stock and image storage keys are
never writable through these serializers.
"""
from rest_framework import serializers
from PIL import Image, UnidentifiedImageError

from apps.catalog.models import (
    Category,
    Collection,
    ColorVariant,
    Product,
    ProductSizeDescription,
    ProductSizeMeasurement,
    Size,
    VariantImage,
    VariantSize,
    VariantSizeDescription,
    VariantSizeMeasurement,
)
from apps.inventory.models import InventoryAdjustment
from apps.inventory.services import adjust_stock
from apps.catalog.storage import public_image_url


class CategoryAdminSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_empty_file=False, write_only=True)
    image_url = serializers.SerializerMethodField()
    remove_image = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = Category
        fields = [
            "id", "name", "slug", "image", "image_url", "remove_image",
            "is_active", "position", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "image_url", "created_at", "updated_at"]

    def get_image_url(self, obj):
        return public_image_url(obj.image.name) if obj.image else None

    def validate_image(self, value):
        if value.size <= 0 or value.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("حجم تصویر باید بیشتر از صفر و حداکثر ۸ مگابایت باشد.")
        try:
            value.seek(0)
            with Image.open(value) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise serializers.ValidationError("فرمت تصویر باید JPEG، PNG یا WebP باشد.")
                if image.width < 1 or image.height < 1 or image.width * image.height > 40_000_000:
                    raise serializers.ValidationError("ابعاد تصویر بیش از حد مجاز است.")
                image.verify()
            value.seek(0)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise serializers.ValidationError("فایل تصویر معتبر یا قابل خواندن نیست.") from exc
        return value

    def validate(self, attrs):
        if attrs.get("remove_image") and attrs.get("image"):
            raise serializers.ValidationError({"image": "برای یک درخواست، تصویر جدید یا حذف تصویر فعلی را انتخاب کنید."})
        return attrs

    def update(self, instance, validated_data):
        remove_image = validated_data.pop("remove_image", False)
        old_image_name = instance.image.name if instance.image else ""
        old_storage = instance.image.storage if instance.image else None
        if remove_image:
            instance.image = ""
        updated = super().update(instance, validated_data)
        if old_image_name and old_storage and (remove_image or updated.image.name != old_image_name):
            old_storage.delete(old_image_name)
        return updated

    def create(self, validated_data):
        validated_data.pop("remove_image", None)
        return super().create(validated_data)


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


class ProductAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id", "product_code", "name", "slug", "description", "price", "sale_price",
            "category", "collections", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


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


class ProductSizeDescriptionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSizeDescription
        fields = ["id", "product", "size", "description"]
        read_only_fields = ["id"]


class VariantSizeDescriptionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantSizeDescription
        fields = ["id", "variant_size", "description"]
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
    created_by_label = serializers.SerializerMethodField()

    def get_created_by_label(self, obj):
        if obj.created_by is None:
            return "سیستم"
        return obj.created_by.phone or obj.created_by.get_username()

    class Meta:
        model = InventoryAdjustment
        fields = [
            "id", "variant_size", "quantity_change", "stock_after",
            "reason", "created_by", "created_by_label", "created_at",
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
