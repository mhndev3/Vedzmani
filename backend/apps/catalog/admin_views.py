"""Permission-checked endpoints for the Persian admin workspace.

The public catalog endpoints remain unchanged. Every endpoint requires both an active staff account and the
relevant Django model permission. Deactivation is used instead of hard deletion; stock changes are routed through
the audited inventory service.
"""
from rest_framework import generics, mixins, viewsets
from rest_framework.permissions import DjangoModelPermissions

from apps.catalog.models import (
    Category,
    Collection,
    ColorVariant,
    Product,
    ProductSizeMeasurement,
    Size,
    VariantImage,
    VariantSize,
    VariantSizeMeasurement,
)
from apps.inventory.models import InventoryAdjustment

from .admin_serializers import (
    CategoryAdminSerializer,
    CollectionAdminSerializer,
    ColorVariantAdminSerializer,
    InventoryAdjustmentAdminSerializer,
    ProductAdminSerializer,
    ProductSizeMeasurementAdminSerializer,
    SizeAdminSerializer,
    VariantImageReadSerializer,
    VariantSizeAdminSerializer,
    VariantSizeMeasurementAdminSerializer,
)


class StaffDjangoModelPermissions(DjangoModelPermissions):
    """Model permissions are necessary, but a permission-bearing customer is never an admin."""

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


class ProductAdminViewSet(StaffModelPermissionViewSet):
    queryset = Product.objects.select_related("category").prefetch_related(
        "collections", "color_variants__sizes__size"
    )
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


class VariantSizeMeasurementAdminViewSet(StaffModelPermissionViewSet):
    queryset = VariantSizeMeasurement.objects.select_related("variant_size__variant__product", "variant_size__size")
    serializer_class = VariantSizeMeasurementAdminSerializer


class VariantImageAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Image metadata is readable; binary upload and storage-key mutation are not exposed yet."""

    queryset = VariantImage.objects.select_related("variant__product").order_by("variant_id", "position", "id")
    serializer_class = VariantImageReadSerializer
    permission_classes = [StaffDjangoModelPermissions]


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
