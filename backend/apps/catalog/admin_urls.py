"""URL map for staff-only admin APIs; mounted under /api/admin/."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import (
    CategoryAdminViewSet,
    CollectionAdminViewSet,
    ColorVariantAdminViewSet,
    InventoryAdjustmentAdminView,
    ProductAdminViewSet,
    ProductSizeMeasurementAdminViewSet,
    SizeAdminViewSet,
    VariantImageAdminViewSet,
    VariantSizeAdminViewSet,
    VariantSizeMeasurementAdminViewSet,
)

router = DefaultRouter()
router.register("catalog/products", ProductAdminViewSet, basename="admin-catalog-product")
router.register("catalog/categories", CategoryAdminViewSet, basename="admin-catalog-category")
router.register("catalog/collections", CollectionAdminViewSet, basename="admin-catalog-collection")
router.register("catalog/sizes", SizeAdminViewSet, basename="admin-catalog-size")
router.register("catalog/colors", ColorVariantAdminViewSet, basename="admin-catalog-color")
router.register("catalog/variant-sizes", VariantSizeAdminViewSet, basename="admin-catalog-variant-size")
router.register("catalog/product-measurements", ProductSizeMeasurementAdminViewSet, basename="admin-catalog-product-measurement")
router.register("catalog/variant-size-measurements", VariantSizeMeasurementAdminViewSet, basename="admin-catalog-variant-size-measurement")
router.register("catalog/images", VariantImageAdminViewSet, basename="admin-catalog-image")

urlpatterns = [
    path("", include(router.urls)),
    path("inventory/adjustments/", InventoryAdjustmentAdminView.as_view(), name="admin-inventory-adjustments"),
]
