"""Atomic staff workflow for creating a product with its colors and size SKUs."""
from uuid import uuid4

from django.db import IntegrityError, transaction
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.validators import UniqueValidator
from rest_framework.views import APIView

from .models import Category, Collection, ColorVariant, Product, Size, VariantSize
from .admin_serializers import ProductAdminSerializer
from apps.inventory.services import adjust_stock
from .product_attributes import clean_optional_marker, clean_product_attributes


class ProductVariantSizeInputSerializer(serializers.Serializer):
    size = serializers.PrimaryKeyRelatedField(queryset=Size.objects.all())
    stock_quantity = serializers.IntegerField(min_value=0, max_value=2**31 - 1, required=False, default=0)
    # SKU is an internal identifier; staff should not have to invent one in the product form.
    sku = serializers.CharField(
        max_length=64,
        trim_whitespace=True,
        validators=[UniqueValidator(queryset=VariantSize.objects.all())],
        required=False,
        allow_blank=True,
        default="",
    )


class ProductColorInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60, trim_whitespace=True)
    slug = serializers.SlugField(max_length=80, required=False, allow_blank=True, default="")
    hex_color = serializers.RegexField(
        regex=r"^#[0-9A-Fa-f]{6}$", required=False, allow_blank=True, default=""
    )
    sizes = ProductVariantSizeInputSerializer(many=True, allow_empty=False)


class ProductWithVariantsInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, trim_whitespace=True)
    slug = serializers.SlugField(max_length=220, required=False, allow_blank=True, default="")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    attributes = serializers.JSONField(required=False, default=dict)
    price = serializers.DecimalField(max_digits=14, decimal_places=0, min_value=1)
    sale_price = serializers.DecimalField(
        max_digits=14, decimal_places=0, min_value=1, required=False, allow_null=True
    )
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True))
    collections = serializers.PrimaryKeyRelatedField(
        queryset=Collection.objects.filter(is_active=True), many=True, required=False
    )
    colors = ProductColorInputSerializer(many=True, allow_empty=False)

    def validate_description(self, value):
        return clean_optional_marker(value)

    def validate(self, attrs):
        attrs["attributes"] = clean_product_attributes(attrs["category"], attrs.get("attributes", {}))
        if not attrs.get("slug"):
            attrs["slug"] = f"product-{uuid4().hex[:16]}"
        sale_price = attrs.get("sale_price")
        if sale_price is not None and sale_price >= attrs["price"]:
            raise serializers.ValidationError({"sale_price": "قیمت با تخفیف باید کمتر از قیمت اصلی باشد."})

        colors = attrs["colors"]
        for color in colors:
            if not color.get("slug"):
                color["slug"] = f"color-{uuid4().hex[:16]}"
        color_slugs = [color["slug"] for color in colors]
        if len(color_slugs) != len(set(color_slugs)):
            raise serializers.ValidationError({"colors": "شناسه انگلیسی رنگ‌ها نباید تکراری باشد."})

        submitted_skus = [
            size["sku"].strip()
            for color in colors
            for size in color["sizes"]
            if size.get("sku", "").strip()
        ]
        if len(submitted_skus) != len(set(submitted_skus)):
            raise serializers.ValidationError({"colors": "SKUها باید در کل محصول یکتا باشند."})

        for color in colors:
            size_ids = [item["size"].pk for item in color["sizes"]]
            if len(size_ids) != len(set(size_ids)):
                raise serializers.ValidationError({"colors": "هر سایز فقط یک‌بار برای هر رنگ قابل ثبت است."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        colors_data = validated_data.pop("colors")
        collections = validated_data.pop("collections", [])
        product = Product.objects.create(**validated_data)
        product.collections.set(collections)

        for color_position, color_data in enumerate(colors_data):
            sizes_data = color_data.pop("sizes")
            color = ColorVariant.objects.create(
                product=product,
                position=color_position,
                **color_data,
            )
            for size_data in sizes_data:
                sku = size_data.get("sku", "").strip()
                if not sku:
                    base_sku = f"VZ-{product.pk}-{color.pk}-{size_data['size'].pk}"
                    sku = base_sku
                    suffix = 1
                    while VariantSize.objects.filter(sku=sku).exists():
                        sku = f"{base_sku}-{suffix}"
                        suffix += 1
                initial_stock = size_data.pop("stock_quantity", 0)
                variant_size = VariantSize.objects.create(variant=color, size=size_data["size"], sku=sku)
                if initial_stock:
                    adjust_stock(
                        variant_size_id=variant_size.pk,
                        quantity_change=initial_stock,
                        reason="موجودی اولیه هنگام ثبت محصول",
                        created_by=self.context["request"].user,
                    )
        return product

    def to_representation(self, instance):
        result = ProductAdminSerializer(instance).data
        result["colors"] = [
            {
                "id": color.pk,
                "name": color.name,
                "slug": color.slug,
                "product_code": color.product_code,
                "hex_color": color.hex_color,
                "is_active": color.is_active,
                "sizes": [
                    {
                        "id": item.pk,
                        "size": item.size_id,
                        "sku": item.sku,
                        "stock_quantity": item.stock_quantity,
                        "is_active": item.is_active,
                    }
                    for item in color.sizes.select_related("size").all()
                ],
            }
            for color in instance.color_variants.order_by("position", "id")
        ]
        return result


class ProductWithVariantsCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        required_permissions = (
            "catalog.add_product",
            "catalog.add_colorvariant",
            "catalog.add_variantsize",
            "catalog.view_variantsize",
            "inventory.add_inventoryadjustment",
        )
        if not user.is_active or not user.is_staff or not all(
            user.has_perm(permission) for permission in required_permissions
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = ProductWithVariantsInputSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            product = serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "یکی از شناسه‌ها یا SKUها قبلاً ثبت شده است؛ اطلاعات را بررسی کنید."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.to_representation(product), status=status.HTTP_201_CREATED)
