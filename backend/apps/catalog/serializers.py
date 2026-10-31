from rest_framework import serializers

from .models import Category, ColorVariant, Product, ProductSizeMeasurement, VariantImage, VariantSize
from .storage import public_image_url


class VariantImageSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = VariantImage
        fields = ["url", "alt_text", "position", "is_primary", "width", "height"]


class ProductSizeMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSizeMeasurement
        fields = ["name", "value", "unit"]


class VariantSizeSerializer(serializers.ModelSerializer):
    size = serializers.CharField(source="size.code")
    label = serializers.CharField(source="size.label")
    in_stock = serializers.SerializerMethodField()
    stock_quantity = serializers.IntegerField(read_only=True)
    measurements = serializers.SerializerMethodField()
    size_description = serializers.SerializerMethodField()

    class Meta:
        model = VariantSize
        fields = ["id", "size", "label", "sku", "in_stock", "stock_quantity", "measurements", "size_description"]

    def get_in_stock(self, obj: VariantSize) -> bool:
        return obj.stock_quantity > 0

    def get_measurements(self, obj: VariantSize):
        # Exact color + size rows win; otherwise fall back to the product + size rows shared by all colors.
        own = list(obj.measurements.all())
        if own:
            return ProductSizeMeasurementSerializer(own, many=True).data
        measurements_by_size = self.context.get("product_measurements_by_size", {})
        return ProductSizeMeasurementSerializer(
            measurements_by_size.get(obj.size_id, []), many=True
        ).data

    def get_size_description(self, obj: VariantSize) -> str:
        # Exact color + size wins; otherwise fall back to the product + size description.
        specific = getattr(obj, "description", None)
        if specific and specific.description.strip():
            return specific.description
        descriptions_by_size = self.context.get("product_size_descriptions_by_size", {})
        return descriptions_by_size.get(obj.size_id, "")


class ColorVariantSerializer(serializers.ModelSerializer):
    images = VariantImageSerializer(many=True, read_only=True)
    sizes = VariantSizeSerializer(many=True, read_only=True)

    class Meta:
        model = ColorVariant
        fields = ["id", "name", "slug", "hex_color", "images", "sizes"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name", "slug"]


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    colors = serializers.SerializerMethodField()
    code = serializers.CharField(source="product_code", read_only=True, allow_null=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "code", "description", "price", "sale_price", "category", "colors"]

    def get_colors(self, obj: Product):
        measurements_by_size = {}
        for measurement in obj.size_measurements.all():
            measurements_by_size.setdefault(measurement.size_id, []).append(measurement)
        descriptions_by_size = {
            description.size_id: description.description
            for description in obj.size_descriptions.all()
        }
        nested_context = {
            **self.context,
            "product_measurements_by_size": measurements_by_size,
            "product_size_descriptions_by_size": descriptions_by_size,
        }
        return ColorVariantSerializer(
            obj.color_variants.all(), many=True, context=nested_context
        ).data


class ColorSwatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorVariant
        fields = ["name", "slug", "hex_color"]


class ProductListSerializer(serializers.ModelSerializer):
    """Product-card representation: one representative image, color swatches, stock flag.

    Relies on annotations/prefetch set up by `filters.build_product_queryset` and the list view.
    """

    category = CategorySerializer(read_only=True)
    code = serializers.CharField(source="product_code", read_only=True, allow_null=True)
    in_stock = serializers.BooleanField(read_only=True)
    image = serializers.SerializerMethodField()
    colors = ColorSwatchSerializer(source="active_colors", many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "code", "price", "sale_price", "category", "in_stock", "image", "colors"]

    def get_image(self, obj: Product):
        if not obj.image_key:
            return None
        return {
            "url": public_image_url(obj.image_key),
            "alt_text": obj.image_alt,
            "width": obj.image_width,
            "height": obj.image_height,
        }
