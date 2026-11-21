"""Permission-checked endpoints for the Persian admin workspace.

The public catalog endpoints remain unchanged. Every endpoint requires both an active staff account and the
relevant Django model permission. Deactivation is used instead of hard deletion; stock changes are routed through
the audited inventory service.
"""
from django.shortcuts import get_object_or_404

from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
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


class CollectionAdminViewSet(StaffModelPermissionViewSet):
    queryset = Collection.objects.all()
    serializer_class = CollectionAdminSerializer


class SizeAdminViewSet(StaffModelPermissionViewSet):
    queryset = Size.objects.all()
    serializer_class = SizeAdminSerializer


class ColorVariantAdminViewSet(StaffModelPermissionViewSet):
    queryset = ColorVariant.objects.select_related("product").prefetch_related("sizes__size")
    serializer_class = ColorVariantAdminSerializer


class VariantSizeAdminViewSet(StaffModelPermissionViewSet):
    queryset = VariantSize.objects.select_related("variant__product", "size")
    serializer_class = VariantSizeAdminSerializer


class ProductSizeMeasurementAdminViewSet(StaffModelPermissionViewSet):
    queryset = ProductSizeMeasurement.objects.select_related("product", "size")
    serializer_class = ProductSizeMeasurementAdminSerializer


class ProductSizeDescriptionAdminViewSet(StaffModelPermissionViewSet):
    queryset = ProductSizeDescription.objects.select_related("product", "size")
    serializer_class = ProductSizeDescriptionAdminSerializer


class VariantSizeDescriptionAdminViewSet(StaffModelPermissionViewSet):
    queryset = VariantSizeDescription.objects.select_related("variant_size__variant__product", "variant_size__size")
    serializer_class = VariantSizeDescriptionAdminSerializer


class VariantSizeMeasurementAdminViewSet(StaffModelPermissionViewSet):
    queryset = VariantSizeMeasurement.objects.select_related("variant_size__variant__product", "variant_size__size")
    serializer_class = VariantSizeMeasurementAdminSerializer


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
    permission_classes = [InventoryAdjustmentPermissions]
    pagination_class = CatalogPagination
