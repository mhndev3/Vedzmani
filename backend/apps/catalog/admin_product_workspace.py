"""Transactional save endpoint for the admin product editor workspace.

The endpoint deliberately composes the existing serializers, inventory service, and image lifecycle helpers.
It does not introduce a second stock writer or bypass image deactivation semantics.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import ColorVariant, Product, VariantImage, VariantSize
from apps.inventory.services import adjust_stock

from .admin_media import deactivate_variant_image, reorder_variant_images
from .admin_serializers import (
    ColorVariantAdminSerializer,
    InventoryAdjustmentAdminSerializer,
    ProductAdminSerializer,
    VariantImageReadSerializer,
    VariantSizeAdminSerializer,
)


class ProductWorkspaceSaveView(APIView):
    """Apply one product editor draft atomically, including audited stock adjustments."""

    permission_classes = [IsAuthenticated]

    def _require(self, user, *permissions):
        if not user.is_staff or not user.is_active or not user.has_perms(permissions):
            raise PermissionDenied("مجوز لازم برای ذخیره همه تغییرات این محصول را ندارید.")

    @transaction.atomic
    def post(self, request, product_id):
        payload = request.data
        if not isinstance(payload, dict):
            raise ValidationError({"detail": "ساختار اطلاعات ارسالی معتبر نیست."})

        product_data = payload.get("product", {})
        colors_data = payload.get("colors", [])
        variant_sizes_data = payload.get("variant_sizes", [])
        images_data = payload.get("images", [])

        if not isinstance(product_data, dict):
            raise ValidationError({"product": "اطلاعات محصول باید یک شیء باشد."})
        for field, value in (
            ("colors", colors_data),
            ("variant_sizes", variant_sizes_data),
            ("images", images_data),
        ):
            if not isinstance(value, list) or len(value) > 200:
                raise ValidationError({field: "فهرست تغییرات معتبر نیست."})

        permissions = ["catalog.change_product"]
        if colors_data:
            permissions.append("catalog.change_colorvariant")
        if variant_sizes_data:
            permissions.append("catalog.change_variantsize")
        if any(isinstance(item, dict) and item.get("quantity_change") not in (None, "", 0, "0") for item in variant_sizes_data):
            permissions.extend(["inventory.add_inventoryadjustment", "catalog.view_variantsize"])
        if images_data:
            permissions.append("catalog.change_variantimage")
        self._require(request.user, *permissions)

        product = get_object_or_404(
            Product.objects.select_for_update().select_related("category").prefetch_related("collections"),
            pk=product_id,
        )

        product_serializer = ProductAdminSerializer(
            product, data=product_data, partial=True, context={"request": request}
        )
        product_serializer.is_valid(raise_exception=True)
        product = product_serializer.save()

        saved_colors = []
        color_ids = set()
        for item in colors_data:
            if not isinstance(item, dict) or not isinstance(item.get("id"), int) or isinstance(item.get("id"), bool):
                raise ValidationError({"colors": "هر تغییر رنگ باید شناسه معتبر داشته باشد."})
            color_id = item["id"]
            if color_id in color_ids:
                raise ValidationError({"colors": "رنگ تکراری در فهرست تغییرات مجاز نیست."})
            color_ids.add(color_id)
            color = get_object_or_404(ColorVariant.objects.select_for_update(), pk=color_id, product=product)
            data = {key: item[key] for key in ("name", "hex_color", "is_active", "position") if key in item}
            serializer = ColorVariantAdminSerializer(
                color, data=data, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            saved_colors.append(serializer.save())

        saved_variant_sizes = []
        adjustments = []
        variant_size_ids = set()
        for item in variant_sizes_data:
            if not isinstance(item, dict) or not isinstance(item.get("id"), int):
                raise ValidationError({"variant_sizes": "هر تغییر سایز باید شناسه معتبر داشته باشد."})
            row_id = item["id"]
            if row_id in variant_size_ids:
                raise ValidationError({"variant_sizes": "ترکیب رنگ و سایز تکراری است."})
            variant_size_ids.add(row_id)
            row = get_object_or_404(
                VariantSize.objects.select_for_update().select_related("variant__product"),
                pk=row_id,
                variant__product=product,
            )
            data = {key: item[key] for key in ("sku", "is_active") if key in item}
            if "sku" in data and (not isinstance(data["sku"], str) or not data["sku"].strip()):
                raise ValidationError({"variant_sizes": "SKU نمی‌تواند خالی باشد."})
            serializer = VariantSizeAdminSerializer(
                row, data=data, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            saved_variant_sizes.append(serializer.save())

            change = item.get("quantity_change")
            if change not in (None, ""):
                if isinstance(change, bool) or not isinstance(change, int) or change == 0:
                    raise ValidationError({"variant_sizes": "تغییر موجودی باید عدد صحیح و غیرصفر باشد."})
                reason = item.get("stock_reason")
                if not isinstance(reason, str) or not reason.strip():
                    raise ValidationError({"variant_sizes": "برای تغییر موجودی، دلیل الزامی است."})
                adjustments.append(adjust_stock(
                    variant_size_id=row.pk,
                    quantity_change=change,
                    reason=reason,
                    created_by=request.user,
                ))

        saved_images = []
        seen_variants = set()
        for item in images_data:
            if not isinstance(item, dict) or not isinstance(item.get("variant"), int) or isinstance(item.get("variant"), bool):
                raise ValidationError({"images": "اطلاعات گروه تصاویر معتبر نیست."})
            variant_id = item["variant"]
            if variant_id in seen_variants:
                raise ValidationError({"images": "هر رنگ فقط یک بار در فهرست تصاویر بیاید."})
            seen_variants.add(variant_id)
            get_object_or_404(ColorVariant.objects.select_for_update(), pk=variant_id, product=product)

            image_ids = item.get("image_ids", [])
            deactivate_ids = item.get("deactivate_ids", [])
            if (
                not isinstance(image_ids, list)
                or not all(isinstance(value, int) and not isinstance(value, bool) for value in image_ids)
                or len(image_ids) != len(set(image_ids))
                or not isinstance(deactivate_ids, list)
                or not all(isinstance(value, int) and not isinstance(value, bool) for value in deactivate_ids)
                or len(deactivate_ids) != len(set(deactivate_ids))
            ):
                raise ValidationError({"images": "شناسه یا ترتیب تصاویر معتبر نیست."})

            active_ids = set(VariantImage.objects.filter(
                variant_id=variant_id, is_active=True
            ).values_list("id", flat=True))
            if set(image_ids) != active_ids:
                raise ValidationError({"images": "ترتیب باید شامل تمام تصاویر فعال این رنگ باشد."})
            if not set(deactivate_ids).issubset(active_ids):
                raise ValidationError({"images": "تصویر برای خارج‌کردن متعلق به این گالری فعال نیست."})

            reorder_variant_images(variant_id=variant_id, image_ids=image_ids)
            for image_id in deactivate_ids:
                deactivate_variant_image(image_id=image_id)
            saved_images.extend(VariantImage.objects.filter(variant_id=variant_id, is_active=True).order_by("position", "id"))

        return Response({
            "product": ProductAdminSerializer(product, context={"request": request}).data,
            "colors": ColorVariantAdminSerializer(saved_colors, many=True, context={"request": request}).data,
            "variant_sizes": VariantSizeAdminSerializer(saved_variant_sizes, many=True, context={"request": request}).data,
            "adjustments": InventoryAdjustmentAdminSerializer(
                adjustments, many=True, context={"request": request}
            ).data,
            "images": VariantImageReadSerializer(saved_images, many=True, context={"request": request}).data,
        }, status=status.HTTP_200_OK)
