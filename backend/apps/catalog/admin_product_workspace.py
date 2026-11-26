"""Transactional save endpoint for the admin product editor workspace.

The endpoint deliberately composes the existing serializers, inventory service, and image lifecycle helpers.
It does not introduce a second stock writer or bypass image deactivation semantics.
"""
import json
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import ColorVariant, Product, Size, VariantImage, VariantSize
from apps.inventory.services import adjust_stock

from .admin_media import deactivate_variant_image, reorder_variant_images, upload_variant_image
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
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _require(self, user, *permissions):
        if not user.is_staff or not user.is_active or not user.has_perms(permissions):
            raise PermissionDenied("مجوز لازم برای ذخیره همه تغییرات این محصول را ندارید.")

    def post(self, request, product_id):
        created_storage_keys = []
        try:
            with transaction.atomic():
                return self._save_workspace(request, product_id, created_storage_keys)
        except Exception:
            # The database transaction cannot roll back filesystem writes. Remove every
            # binary created by this request if validation, serialization, or commit fails.
            media_root = Path(settings.MEDIA_ROOT).resolve()
            for key in created_storage_keys:
                target = (media_root / key).resolve()
                try:
                    target.relative_to(media_root)
                except ValueError:
                    continue
                target.unlink(missing_ok=True)
            raise

    def _save_workspace(self, request, product_id, created_storage_keys):
        payload = request.data
        if "workspace" in payload:
            try:
                payload = json.loads(payload.get("workspace") or "")
            except (TypeError, ValueError) as exc:
                raise ValidationError({"workspace": "ساختار پیش‌نویس معتبر نیست."}) from exc
        if not isinstance(payload, dict):
            raise ValidationError({"detail": "ساختار اطلاعات ارسالی معتبر نیست."})

        product_data = payload.get("product", {})
        colors_data = payload.get("colors", [])
        variant_sizes_data = payload.get("variant_sizes", [])
        images_data = payload.get("images", [])
        new_colors_data = payload.get("new_colors", [])
        new_variant_sizes_data = payload.get("new_variant_sizes", [])

        if not isinstance(product_data, dict):
            raise ValidationError({"product": "اطلاعات محصول باید یک شیء باشد."})
        for field, value in (
            ("colors", colors_data),
            ("variant_sizes", variant_sizes_data),
            ("images", images_data),
            ("new_colors", new_colors_data),
            ("new_variant_sizes", new_variant_sizes_data),
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
        has_new_images = any(
            isinstance(item, dict) and item.get("new_images")
            for item in images_data
        )
        if has_new_images:
            permissions.extend(["catalog.add_variantimage", "catalog.view_colorvariant"])
        if new_colors_data:
            permissions.append("catalog.add_colorvariant")
        if new_variant_sizes_data or any(isinstance(item, dict) and item.get("sizes") for item in new_colors_data):
            permissions.append("catalog.add_variantsize")
        has_initial_stock = any(
            isinstance(item, dict) and item.get("initial_stock", 0) not in (None, "", 0, "0")
            for item in new_variant_sizes_data
        )
        for color_item in new_colors_data:
            if isinstance(color_item, dict) and isinstance(color_item.get("sizes"), list):
                has_initial_stock = has_initial_stock or any(
                    isinstance(size_item, dict)
                    and size_item.get("initial_stock", 0) not in (None, "", 0, "0")
                    for size_item in color_item["sizes"]
                )
        if has_initial_stock:
            permissions.extend(["inventory.add_inventoryadjustment", "catalog.view_variantsize"])
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
        saved_variant_sizes = []
        adjustments = []
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

        # New colors and their size combinations are created only when the whole workspace is saved.
        # All rows remain inside this transaction, including audited opening-stock adjustments.
        for color_item in new_colors_data:
            if not isinstance(color_item, dict):
                raise ValidationError({"new_colors": "اطلاعات رنگ جدید معتبر نیست."})
            name = color_item.get("name")
            hex_color = color_item.get("hex_color", "#000000")
            if not isinstance(name, str) or not name.strip():
                raise ValidationError({"new_colors": "نام رنگ نمی‌تواند خالی باشد."})
            color_position = color_item.get("position", product.color_variants.count())
            color_serializer = ColorVariantAdminSerializer(
                data={
                    "product": product.pk,
                    "name": name.strip(),
                    "hex_color": hex_color,
                    "position": color_position,
                    "is_active": True,
                },
                context={"request": request},
            )
            color_serializer.is_valid(raise_exception=True)
            created_color = color_serializer.save()
            saved_colors.append(created_color)

            sizes = color_item.get("sizes", [])
            if not isinstance(sizes, list) or len(sizes) > 100:
                raise ValidationError({"new_colors": "فهرست سایزهای رنگ جدید معتبر نیست."})
            seen_sizes = set()
            for size_item in sizes:
                if not isinstance(size_item, dict):
                    raise ValidationError({"new_colors": "اطلاعات سایز جدید معتبر نیست."})
                size_id = size_item.get("size")
                if isinstance(size_id, bool) or not isinstance(size_id, int) or size_id in seen_sizes:
                    raise ValidationError({"new_colors": "شناسه سایز معتبر یا یکتا نیست."})
                seen_sizes.add(size_id)
                if not product.category.sizes.filter(pk=size_id).exists():
                    raise ValidationError({"new_colors": "این سایز برای دسته‌بندی محصول مجاز نیست."})
                size = get_object_or_404(Size, pk=size_id)
                variant_size_serializer = VariantSizeAdminSerializer(
                    data={"variant": created_color.pk, "size": size.pk},
                    context={"request": request},
                )
                variant_size_serializer.is_valid(raise_exception=True)
                created_variant_size = variant_size_serializer.save()
                saved_variant_sizes.append(created_variant_size)

                initial_stock = size_item.get("initial_stock", 0)
                if isinstance(initial_stock, bool) or not isinstance(initial_stock, int) or initial_stock < 0 or initial_stock > 2147483647:
                    raise ValidationError({"new_colors": "موجودی اولیه باید عدد صحیح و نامنفی باشد."})
                if initial_stock:
                    adjustments.append(adjust_stock(
                        variant_size_id=created_variant_size.pk,
                        quantity_change=initial_stock,
                        reason="موجودی اولیه هنگام ساخت ترکیب رنگ و سایز",
                        created_by=request.user,
                    ))

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

        for item in new_variant_sizes_data:
            if not isinstance(item, dict):
                raise ValidationError({"new_variant_sizes": "اطلاعات سایز جدید معتبر نیست."})
            variant_id = item.get("variant")
            size_id = item.get("size")
            if (
                isinstance(variant_id, bool) or not isinstance(variant_id, int)
                or isinstance(size_id, bool) or not isinstance(size_id, int)
            ):
                raise ValidationError({"new_variant_sizes": "شناسه رنگ یا سایز معتبر نیست."})
            color = get_object_or_404(
                ColorVariant.objects.select_for_update(), pk=variant_id, product=product
            )
            if not product.category.sizes.filter(pk=size_id).exists():
                raise ValidationError({"new_variant_sizes": "این سایز برای دسته‌بندی محصول مجاز نیست."})
            if VariantSize.objects.filter(variant=color, size_id=size_id).exists():
                raise ValidationError({"new_variant_sizes": "این سایز قبلاً برای این رنگ ثبت شده است."})
            size = get_object_or_404(Size, pk=size_id)
            serializer = VariantSizeAdminSerializer(
                data={"variant": color.pk, "size": size.pk},
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            created_variant_size = serializer.save()
            saved_variant_sizes.append(created_variant_size)

            initial_stock = item.get("initial_stock", 0)
            if isinstance(initial_stock, bool) or not isinstance(initial_stock, int) or initial_stock < 0 or initial_stock > 2147483647:
                raise ValidationError({"new_variant_sizes": "موجودی اولیه باید عدد صحیح و نامنفی باشد."})
            if initial_stock:
                adjustments.append(adjust_stock(
                    variant_size_id=created_variant_size.pk,
                    quantity_change=initial_stock,
                    reason="موجودی اولیه هنگام افزودن سایز به رنگ",
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
            new_images = item.get("new_images", [])
            order = item.get("order")
            if (
                not isinstance(image_ids, list)
                or not all(isinstance(value, int) and not isinstance(value, bool) for value in image_ids)
                or len(image_ids) != len(set(image_ids))
                or not isinstance(deactivate_ids, list)
                or not all(isinstance(value, int) and not isinstance(value, bool) for value in deactivate_ids)
                or len(deactivate_ids) != len(set(deactivate_ids))
                or not isinstance(new_images, list)
                or len(new_images) > 20
            ):
                raise ValidationError({"images": "شناسه یا فهرست تصاویر معتبر نیست."})

            active_ids = set(VariantImage.objects.filter(
                variant_id=variant_id, is_active=True
            ).values_list("id", flat=True))
            if not set(deactivate_ids).issubset(active_ids):
                raise ValidationError({"images": "تصویر برای خارج‌کردن متعلق به این گالری فعال نیست."})
            remaining_ids = active_ids - set(deactivate_ids)

            new_by_key = {}
            for new_item in new_images:
                if not isinstance(new_item, dict):
                    raise ValidationError({"images": "اطلاعات تصویر جدید معتبر نیست."})
                key = new_item.get("key")
                alt_text = new_item.get("alt_text", "")
                if not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{32}", key):
                    raise ValidationError({"images": "شناسه تصویر جدید معتبر نیست."})
                if key in new_by_key or not isinstance(alt_text, str):
                    raise ValidationError({"images": "شناسه یا متن جایگزین تصویر تکراری یا نامعتبر است."})
                upload = request.FILES.get(f"image_{key}")
                if upload is None:
                    raise ValidationError({"images": "فایل یکی از تصاویر پیش‌نویس ارسال نشده است."})
                new_by_key[key] = {"upload": upload, "alt_text": alt_text[:200]}

            if order is None:
                # Backwards compatibility for callers that only reorder existing images.
                if set(image_ids) != active_ids:
                    raise ValidationError({"images": "ترتیب باید شامل تمام تصاویر فعال این رنگ باشد."})
                ordered_tokens = [f"existing:{image_id}" for image_id in image_ids if image_id not in deactivate_ids]
            else:
                if not isinstance(order, list) or len(order) > 100:
                    raise ValidationError({"images": "ترتیب تصاویر معتبر نیست."})
                ordered_tokens = order
                parsed_existing = []
                parsed_new = []
                for token in ordered_tokens:
                    if not isinstance(token, str):
                        raise ValidationError({"images": "ترتیب تصاویر معتبر نیست."})
                    if token.startswith("existing:") and token[9:].isdigit():
                        parsed_existing.append(int(token[9:]))
                    elif token.startswith("new:") and re.fullmatch(r"[a-f0-9]{32}", token[4:]):
                        parsed_new.append(token[4:])
                    else:
                        raise ValidationError({"images": "شناسه یکی از تصاویر در ترتیب معتبر نیست."})
                if len(parsed_existing) != len(set(parsed_existing)) or set(parsed_existing) != remaining_ids:
                    raise ValidationError({"images": "ترتیب باید شامل تمام تصاویر باقی‌مانده همین رنگ باشد."})
                if len(parsed_new) != len(set(parsed_new)) or set(parsed_new) != set(new_by_key):
                    raise ValidationError({"images": "ترتیب باید شامل تمام تصاویر جدید پیش‌نویس باشد."})

            for image_id in deactivate_ids:
                deactivate_variant_image(image_id=image_id)

            created_ids_by_key = {}
            for token in ordered_tokens:
                if token.startswith("new:"):
                    key = token[4:]
                    image_data = new_by_key[key]
                    image = upload_variant_image(
                        variant_id=variant_id,
                        upload=image_data["upload"],
                        alt_text=image_data["alt_text"],
                    )
                    created_storage_keys.append(image.storage_key)
                    created_ids_by_key[key] = image.pk

            final_ids = [
                int(token[9:]) if token.startswith("existing:") else created_ids_by_key[token[4:]]
                for token in ordered_tokens
            ]
            if final_ids:
                reorder_variant_images(variant_id=variant_id, image_ids=final_ids)
            saved_images.extend(
                VariantImage.objects.filter(variant_id=variant_id, is_active=True).order_by("position", "id")
            )

        return Response({
            "product": ProductAdminSerializer(product, context={"request": request}).data,
            "colors": ColorVariantAdminSerializer(saved_colors, many=True, context={"request": request}).data,
            "variant_sizes": VariantSizeAdminSerializer(saved_variant_sizes, many=True, context={"request": request}).data,
            "adjustments": InventoryAdjustmentAdminSerializer(
                adjustments, many=True, context={"request": request}
            ).data,
            "images": VariantImageReadSerializer(saved_images, many=True, context={"request": request}).data,
        }, status=status.HTTP_200_OK)
