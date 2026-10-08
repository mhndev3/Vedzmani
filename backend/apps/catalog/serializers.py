from rest_framework import serializers

from .models import Category, ColorVariant, Product, VariantImage, VariantSize


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
