"""Staff-only serializers for the custom catalog workspace API.

All write paths deliberately expose model fields rather than accepting arbitrary nested object graphs.
Related records are managed through their own permission-checked endpoints. Stock and image storage keys are
never writable through these serializers.
"""
from uuid import uuid4

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
from apps.catalog.product_attributes import clean_optional_marker, clean_product_attributes, validate_product_field_schema


class CategoryAdminSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_empty_file=False, write_only=True)
    image_url = serializers.SerializerMethodField()
    remove_image = serializers.BooleanField(required=False, write_only=True)
    product_fields = serializers.JSONField(required=False)
    sizes = serializers.SerializerMethodField()
    size_ids = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = Category
        fields = [
            "id", "name", "slug", "image", "image_url", "remove_image", "product_fields",
            "sizes", "size_ids", "is_active", "position", "is_homepage_featured", "homepage_position", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "image_url", "created_at", "updated_at"]

    def get_image_url(self, obj):
        return public_image_url(obj.image.name) if obj.image else None

    def get_sizes(self, obj):
        return list(obj.sizes.order_by("position", "id").values_list("id", flat=True))

    def validate_size_ids(self, value):
        if not isinstance(value, list) or any(
            isinstance(item, bool) or not isinstance(item, int) or item <= 0
            for item in value
        ):
            raise serializers.ValidationError("فهرست سایزهای دسته‌بندی معتبر نیست.")
        if len(value) != len(set(value)):
            raise serializers.ValidationError("سایز تکراری در فهرست دسته‌بندی مجاز نیست.")
        if Size.objects.filter(pk__in=value).count() != len(value):
            raise serializers.ValidationError("یکی از سایزهای انتخاب‌شده وجود ندارد.")
        return value

    def create(self, validated_data):
        size_ids = validated_data.pop("size_ids", None)
        validated_data.pop("remove_image", None)
        instance = super().create(validated_data)
        if size_ids is not None:
            instance.sizes.set(size_ids)
        return instance

    def update(self, instance, validated_data):
        size_ids = validated_data.pop("size_ids", None)
        remove_image = validated_data.pop("remove_image", False)
        old_image_name = instance.image.name if instance.image else ""
        old_storage = instance.image.storage if instance.image else None
        if remove_image:
            instance.image = ""
        updated = super().update(instance, validated_data)
        if size_ids is not None:
            updated.sizes.set(size_ids)
        if old_image_name and old_storage and (remove_image or updated.image.name != old_image_name):
            old_storage.delete(old_image_name)
        return updated

    def validate_product_fields(self, value):
        return validate_product_field_schema(value)

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



class CollectionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = ["id", "name", "slug", "is_active", "position", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SizeAdminSerializer(serializers.ModelSerializer):
    # Store managers enter the visible label; the internal API code is generated
    # when omitted so Persian size labels do not require a technical identifier.
    code = serializers.SlugField(max_length=20, required=False, allow_blank=True)

    class Meta:
        model = Size
        fields = ["id", "code", "label", "position"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        if not validated_data.get("code"):
            validated_data["code"] = f"size-{uuid4().hex[:12]}"
        return super().create(validated_data)


class ProductAdminSerializer(serializers.ModelSerializer):
    attributes = serializers.JSONField(required=False)

    class Meta:
        model = Product
        fields = [
            "id", "product_code", "name", "slug", "description", "attributes", "price", "sale_price",
            "category", "collections", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_description(self, value):
        return clean_optional_marker(value)

    def validate(self, attrs):
        category = attrs.get("category", self.instance.category if self.instance else None)
        attributes = attrs.get("attributes", self.instance.attributes if self.instance else {})
        if category is not None:
            cleaned_attributes = clean_product_attributes(
                category,
                attributes,
                reject_unknown="attributes" in attrs,
                enforce_required=("attributes" in attrs or "category" in attrs or self.instance is None),
            )
            if self.instance is not None:
                # Preserve values outside the selected category schema. The admin editor only
                # exposes active category fields, so dropping other keys would destroy legacy data.
                submitted_attributes = attrs.get("attributes", {})
                for key, value in (self.instance.attributes or {}).items():
                    if key not in cleaned_attributes and key not in submitted_attributes:
                        cleaned_attributes[key] = value
            attrs["attributes"] = cleaned_attributes

        # Validate the final effective values, not only fields included in a PATCH.
        # Otherwise changing the base price could silently leave a discount at or above it.
        price = attrs.get("price", self.instance.price if self.instance else None)
        sale_price = attrs.get("sale_price", self.instance.sale_price if self.instance else None)
        if sale_price is not None and price is not None and sale_price >= price:
            raise serializers.ValidationError({
                "sale_price": "قیمت با تخفیف باید کمتر از قیمت اصلی باشد."
            })
        return attrs


class ImmutableVariantAssociationMixin:
    immutable_association_fields = ()

    def validate(self, attrs):
        if self.instance is not None:
            attempted = [
                field for field in self.immutable_association_fields
                if field in self.initial_data
            ]
            if attempted:
                raise serializers.ValidationError({
                    field: "ارتباط این رکورد پس از ساخت قابل تغییر نیست؛ ترکیب جدید بسازید و رکورد قبلی را غیرفعال کنید."
                    for field in attempted
                })
        return super().validate(attrs)


class ColorVariantAdminSerializer(ImmutableVariantAssociationMixin, serializers.ModelSerializer):
    immutable_association_fields = ("product",)
    slug = serializers.SlugField(max_length=80, required=False, allow_blank=True)

    class Meta:
        model = ColorVariant
        fields = [
            "id", "product", "name", "slug", "product_code", "hex_color",
            "is_active", "position", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "product_code", "created_at", "updated_at"]
        # The model's unique (product, slug) constraint otherwise makes DRF
        # mark slug required even though create() generates it automatically.
        validators = []

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = f"color-{uuid4().hex[:16]}"
        return super().create(validated_data)


class VariantSizeAdminSerializer(ImmutableVariantAssociationMixin, serializers.ModelSerializer):
    immutable_association_fields = ("variant", "size")
    class Meta:
        model = VariantSize
        fields = ["id", "variant", "size", "sku", "stock_quantity", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "stock_quantity", "created_at", "updated_at"]
        extra_kwargs = {"sku": {"required": False, "allow_blank": True}}

    def create(self, validated_data):
        if not validated_data.get("sku", "").strip():
            variant = validated_data["variant"]
            size = validated_data["size"]
            base_sku = f"VZ-{variant.product_id}-{variant.pk}-{size.pk}"
            sku = base_sku
            suffix = 1
            while VariantSize.objects.filter(sku=sku).exists():
                sku = f"{base_sku}-{suffix}"
                suffix += 1
            validated_data["sku"] = sku
        else:
            validated_data["sku"] = validated_data["sku"].strip()
        return super().create(validated_data)


class ProductSizeMeasurementAdminSerializer(serializers.ModelSerializer):
    name = serializers.CharField(allow_blank=True, required=True)
    value = serializers.CharField(allow_blank=True, required=True)
    unit = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = ProductSizeMeasurement
        fields = ["id", "product", "size", "name", "value", "unit", "position"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        for field in ("name", "value", "unit"):
            if field in attrs:
                attrs[field] = clean_optional_marker(attrs[field])
        return attrs


class ProductSizeDescriptionAdminSerializer(serializers.ModelSerializer):
    description = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = ProductSizeDescription
        fields = ["id", "product", "size", "description"]
        read_only_fields = ["id"]

    def validate_description(self, value):
        return clean_optional_marker(value)


class VariantSizeDescriptionAdminSerializer(serializers.ModelSerializer):
    description = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = VariantSizeDescription
        fields = ["id", "variant_size", "description"]
        read_only_fields = ["id"]

    def validate_description(self, value):
        return clean_optional_marker(value)


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
