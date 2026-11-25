"""Permission-checked endpoints for the Persian admin workspace.

The public catalog endpoints remain unchanged. Every endpoint requires both an active staff account and the
relevant Django model permission. Deactivation is used instead of hard deletion; stock changes are routed through
the audited inventory service.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

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

from .admin_media import deactivate_variant_image, reorder_variant_images, upload_variant_image
from .pagination import CatalogPagination

from .admin_serializers import (
    CategoryAdminSerializer,
    CollectionAdminSerializer,
    ColorVariantAdminSerializer,
    InventoryAdjustmentAdminSerializer,
    ProductAdminSerializer,
    ProductSizeDescriptionAdminSerializer,
    ProductSizeMeasurementAdminSerializer,
    SizeAdminSerializer,
    VariantImageReadSerializer,
    VariantSizeAdminSerializer,
    VariantSizeDescriptionAdminSerializer,
    VariantSizeMeasurementAdminSerializer,
)


class StaffDjangoModelPermissions(DjangoModelPermissions):
    """Require staff status and explicit model permissions for reads and writes."""

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff and super().has_permission(request, view))


class MeasurementReorderPermissions(StaffDjangoModelPermissions):
    """Custom POST reorder actions mutate existing rows, so they require change, not add permission."""

    def has_permission(self, request, view):
        if getattr(view, "action", None) != "reorder":
            return super().has_permission(request, view)
        user = request.user
        queryset = getattr(view, "queryset", None)
        model = getattr(queryset, "model", None)
        if not user or not user.is_authenticated or not user.is_staff or model is None:
            return False
        opts = model._meta
        return user.has_perm(f"{opts.app_label}.change_{opts.model_name}")


def _reorder_measurement_rows(queryset, ordered_ids):
    """Reorder one complete parent-scoped set without violating its unique position constraint."""
    with transaction.atomic():
        rows = list(queryset.select_for_update().order_by("position", "id"))
        current_ids = {row.pk for row in rows}
        if len(ordered_ids) != len(current_ids) or set(ordered_ids) != current_ids:
            raise ValidationError({
                "measurement_ids": "فهرست باید شامل تمام اندازه‌های همین گروه، بدون تکرار باشد."
            })
        if not rows:
            return []

        model = queryset.model
        offset = max(row.position for row in rows) + len(rows) + 1
        # Move every row out of the destination range first, avoiding transient unique collisions.
        for row in rows:
            model.objects.filter(pk=row.pk).update(position=row.position + offset)
        for position, row_id in enumerate(ordered_ids):
            model.objects.filter(pk=row_id).update(position=position)
        return list(queryset.order_by("position", "id"))


def _validated_measurement_ids(value):
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in value
    ):
        raise ValidationError({"measurement_ids": "شناسه اندازه‌ها باید فهرستی از اعداد صحیح مثبت باشد."})
    if len(value) != len(set(value)):
        raise ValidationError({"measurement_ids": "شناسه تکراری در فهرست اندازه‌ها مجاز نیست."})
    return value


class TaxonomyReorderPermissions(StaffDjangoModelPermissions):
    """Taxonomy reorder actions mutate existing rows and require change permission."""

    def has_permission(self, request, view):
        if getattr(view, "action", None) != "reorder":
            return super().has_permission(request, view)
        user = request.user
        model = getattr(getattr(view, "queryset", None), "model", None)
        if not user or not user.is_authenticated or not user.is_staff or model is None:
            return False
        return user.has_perm(f"{model._meta.app_label}.change_{model._meta.model_name}")


def _reorder_taxonomy_rows(queryset, ordered_ids):
    """Atomically apply a complete ordering for categories or collections."""
    with transaction.atomic():
        rows = list(queryset.select_for_update().order_by("position", "id"))
        current_ids = {row.pk for row in rows}
        if len(ordered_ids) != len(current_ids) or set(ordered_ids) != current_ids:
            raise ValidationError({"entry_ids": "فهرست باید شامل تمام موارد همین گروه، بدون تکرار باشد."})
        if not rows:
            return []
        model = queryset.model
        offset = max(row.position for row in rows) + len(rows) + 1
        for row in rows:
            model.objects.filter(pk=row.pk).update(position=row.position + offset)
        for position, row_id in enumerate(ordered_ids):
            model.objects.filter(pk=row_id).update(position=position)
        return list(queryset.order_by("position", "id"))


def _validated_taxonomy_ids(value):
    if not isinstance(value, list) or not all(isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in value):
        raise ValidationError({"entry_ids": "شناسه‌ها باید فهرستی از اعداد صحیح مثبت باشند."})
    # Completeness and duplicate checks are performed together against the
    # locked parent-scoped queryset in _reorder_taxonomy_rows.
    return value

class StaffModelPermissionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Create/read/update only; deactivation replaces hard deletion in this API."""

    permission_classes = [StaffDjangoModelPermissions]
    pagination_class = CatalogPagination


class ProductAdminViewSet(StaffModelPermissionViewSet):
    queryset = Product.objects.select_related("category").prefetch_related("collections")
    serializer_class = ProductAdminSerializer


class CategoryAdminViewSet(StaffModelPermissionViewSet):
    queryset = Category.objects.all()
    serializer_class = CategoryAdminSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [TaxonomyReorderPermissions]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        ordered_ids = _validated_taxonomy_ids(request.data.get("entry_ids"))
        rows = _reorder_taxonomy_rows(Category.objects.all(), ordered_ids)
        return Response(self.get_serializer(rows, many=True).data)


class CollectionAdminViewSet(StaffModelPermissionViewSet):
    queryset = Collection.objects.all()
    serializer_class = CollectionAdminSerializer
    permission_classes = [TaxonomyReorderPermissions]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        ordered_ids = _validated_taxonomy_ids(request.data.get("entry_ids"))
        rows = _reorder_taxonomy_rows(Collection.objects.all(), ordered_ids)
        return Response(self.get_serializer(rows, many=True).data)


class SizeAdminViewSet(StaffModelPermissionViewSet):
    queryset = Size.objects.all()
    serializer_class = SizeAdminSerializer


class ColorVariantAdminViewSet(StaffModelPermissionViewSet):
    queryset = ColorVariant.objects.select_related("product").prefetch_related("sizes__size")
    serializer_class = ColorVariantAdminSerializer
    permission_classes = [TaxonomyReorderPermissions]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        product_id = request.data.get("product")
        if not str(product_id or "").isdigit() or int(product_id) < 1:
            raise ValidationError({"product": "شناسه محصول معتبر نیست."})
        ordered_ids = _validated_taxonomy_ids(request.data.get("entry_ids"))
        rows = _reorder_taxonomy_rows(
            ColorVariant.objects.filter(product_id=int(product_id)),
            ordered_ids,
        )
        return Response(self.get_serializer(rows, many=True).data)


class VariantSizeAdminViewSet(StaffModelPermissionViewSet):
    queryset = VariantSize.objects.select_related("variant__product", "size")
    serializer_class = VariantSizeAdminSerializer


class ProductSizeMeasurementAdminViewSet(StaffModelPermissionViewSet):
    queryset = ProductSizeMeasurement.objects.select_related("product", "size")
    serializer_class = ProductSizeMeasurementAdminSerializer
    permission_classes = [MeasurementReorderPermissions]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        product_id = request.data.get("product")
        size_id = request.data.get("size")
        if not str(product_id or "").isdigit() or int(product_id) < 1:
            raise ValidationError({"product": "شناسه محصول معتبر نیست."})
        if not str(size_id or "").isdigit() or int(size_id) < 1:
            raise ValidationError({"size": "شناسه سایز معتبر نیست."})
        ordered_ids = _validated_measurement_ids(request.data.get("measurement_ids"))
        rows = _reorder_measurement_rows(
            ProductSizeMeasurement.objects.filter(product_id=int(product_id), size_id=int(size_id)),
            ordered_ids,
        )
        return Response(self.get_serializer(rows, many=True).data)


class ProductSizeDescriptionAdminViewSet(StaffModelPermissionViewSet):
    queryset = ProductSizeDescription.objects.select_related("product", "size")
    serializer_class = ProductSizeDescriptionAdminSerializer


class VariantSizeDescriptionAdminViewSet(StaffModelPermissionViewSet):
    queryset = VariantSizeDescription.objects.select_related("variant_size__variant__product", "variant_size__size")
    serializer_class = VariantSizeDescriptionAdminSerializer


class VariantSizeMeasurementAdminViewSet(StaffModelPermissionViewSet):
    queryset = VariantSizeMeasurement.objects.select_related("variant_size__variant__product", "variant_size__size")
    serializer_class = VariantSizeMeasurementAdminSerializer
    permission_classes = [MeasurementReorderPermissions]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        variant_size_id = request.data.get("variant_size")
        if not str(variant_size_id or "").isdigit() or int(variant_size_id) < 1:
            raise ValidationError({"variant_size": "شناسه ترکیب رنگ و سایز معتبر نیست."})
        ordered_ids = _validated_measurement_ids(request.data.get("measurement_ids"))
        rows = _reorder_measurement_rows(
            VariantSizeMeasurement.objects.filter(variant_size_id=int(variant_size_id)),
            ordered_ids,
        )
        return Response(self.get_serializer(rows, many=True).data)


class VariantImageAdminPermissions(StaffDjangoModelPermissions):
    """Map image actions to the exact model permission they mutate."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_staff:
            return False
        action_name = getattr(view, "action", None)
        permission = {
            "list": "catalog.view_variantimage",
            "retrieve": "catalog.view_variantimage",
            "upload": "catalog.add_variantimage",
            "reorder": "catalog.change_variantimage",
            "deactivate": "catalog.change_variantimage",
        }.get(action_name)
        if not permission or not user.has_perm(permission):
            return False
        if action_name == "upload":
            return user.has_perm("catalog.view_colorvariant")
        return True


class VariantImageAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Staff-only image upload, ordering, primary selection, and safe deactivation."""

    queryset = VariantImage.objects.select_related("variant__product").order_by("variant_id", "position", "id")
    serializer_class = VariantImageReadSerializer
    permission_classes = [VariantImageAdminPermissions]
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        variant_id = self.request.query_params.get("variant")
        if variant_id:
            queryset = queryset.filter(variant_id=variant_id)
        return queryset

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser], url_path="upload")
    def upload(self, request):
        variant_id = request.data.get("variant")
        if not str(variant_id or "").isdigit():
            raise ValidationError({"variant": "رنگ محصول معتبر نیست."})
        variant = get_object_or_404(ColorVariant, pk=int(variant_id))
        image = upload_variant_image(
            variant_id=variant.pk,
            upload=request.FILES.get("file"),
            alt_text=str(request.data.get("alt_text") or ""),
        )
        return Response(self.get_serializer(image).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        variant_id = request.data.get("variant")
        image_ids = request.data.get("image_ids")
        if not str(variant_id or "").isdigit() or not isinstance(image_ids, list):
            raise ValidationError({"detail": "رنگ و فهرست تصاویر الزامی است."})
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in image_ids):
            raise ValidationError({"image_ids": "شناسه تصاویر باید عدد صحیح باشد."})
        images = reorder_variant_images(variant_id=int(variant_id), image_ids=image_ids)
        return Response(self.get_serializer(images, many=True).data)

    @action(detail=True, methods=["patch"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        image = get_object_or_404(VariantImage, pk=pk, is_active=True)
        image = deactivate_variant_image(image_id=image.pk)
        return Response(self.get_serializer(image).data)


class InventoryAdjustmentPermissions(StaffDjangoModelPermissions):
    """Stock writers must also be allowed to inspect the stock item they are changing."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.method != "POST" or request.user.has_perm("catalog.view_variantsize")


class InventoryAdjustmentAdminView(generics.ListCreateAPIView):
    """Read the append-only stock audit log or create an adjustment through the locking service."""

    queryset = InventoryAdjustment.objects.select_related(
        "variant_size__variant__product", "variant_size__size", "created_by"
    )
    serializer_class = InventoryAdjustmentAdminSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        variant_size = self.request.query_params.get("variant_size")
        if variant_size is not None:
            if not variant_size.isdigit():
                raise ValidationError({"variant_size": "شناسه سایز معتبر نیست."})
            queryset = queryset.filter(variant_size_id=int(variant_size))
        return queryset
    permission_classes = [InventoryAdjustmentPermissions]
    pagination_class = CatalogPagination
