from rest_framework import serializers

from .models import Category, ColorVariant, Product, VariantImage, VariantSize
from .storage import public_image_url


class VariantImageSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = VariantImage
        fields = ["url", "alt_text", "position", "is_primary", "width", "height"]


class VariantSizeSerializer(serializers.ModelSerializer):
    size = serializers.CharField(source="size.code")
    label = serializers.CharField(source="size.label")
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = VariantSize
        fields = ["id", "size", "label", "sku", "in_stock"]

    def get_in_stock(self, obj: VariantSize) -> bool:
        return obj.stock_quantity > 0


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
    colors = ColorVariantSerializer(source="color_variants", many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "description", "price", "sale_price", "category", "colors"]


class ColorSwatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorVariant
        fields = ["name", "slug", "hex_color"]


class ProductListSerializer(serializers.ModelSerializer):
    """Product-card representation: one representative image, color swatches, stock flag.

    Relies on annotations/prefetch set up by `filters.build_product_queryset` and the list view.
    """

    category = CategorySerializer(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    image = serializers.SerializerMethodField()
    colors = ColorSwatchSerializer(source="active_colors", many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "price", "sale_price", "category", "in_stock", "image", "colors"]

    def get_image(self, obj: Product):
        if not obj.image_key:
            return None
        return {
            "url": public_image_url(obj.image_key),
            "alt_text": obj.image_alt,
            "width": obj.image_width,
            "height": obj.image_height,
        }
