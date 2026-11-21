"""URL map for staff-only admin APIs; mounted under /api/admin/."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.orders.admin_api import AdminOrderDetailView, AdminOrderListView
from .homepage_admin import HomepageSectionAdminViewSet
from .homepage_banner_admin import HomepageBannerAdminViewSet
from .storefront_theme import StorefrontThemeAdminView
from .admin_views import (
    CategoryAdminViewSet,
    CollectionAdminViewSet,
    ColorVariantAdminViewSet,
    InventoryAdjustmentAdminView,
    ProductAdminViewSet,
    ProductSizeDescriptionAdminViewSet,
    ProductSizeMeasurementAdminViewSet,
    SizeAdminViewSet,
    VariantImageAdminViewSet,
    VariantSizeAdminViewSet,
    VariantSizeDescriptionAdminViewSet,
    VariantSizeMeasurementAdminViewSet,
)

router = DefaultRouter()
router.register("homepage/sections", HomepageSectionAdminViewSet, basename="admin-homepage-section")
router.register("homepage/banners", HomepageBannerAdminViewSet, basename="admin-homepage-banner")
router.register("catalog/products", ProductAdminViewSet, basename="admin-catalog-product")
router.register("catalog/categories", CategoryAdminViewSet, basename="admin-catalog-category")
router.register("catalog/collections", CollectionAdminViewSet, basename="admin-catalog-collection")
router.register("catalog/sizes", SizeAdminViewSet, basename="admin-catalog-size")
router.register("catalog/colors", ColorVariantAdminViewSet, basename="admin-catalog-color")
router.register("catalog/variant-sizes", VariantSizeAdminViewSet, basename="admin-catalog-variant-size")
router.register("catalog/product-measurements", ProductSizeMeasurementAdminViewSet, basename="admin-catalog-product-measurement")
router.register("catalog/product-size-descriptions", ProductSizeDescriptionAdminViewSet, basename="admin-catalog-product-size-description")
router.register("catalog/variant-size-measurements", VariantSizeMeasurementAdminViewSet, basename="admin-catalog-variant-size-measurement")
router.register("catalog/variant-size-descriptions", VariantSizeDescriptionAdminViewSet, basename="admin-catalog-variant-size-description")
router.register("catalog/images", VariantImageAdminViewSet, basename="admin-catalog-image")

urlpatterns = [
    path("storefront/theme/", StorefrontThemeAdminView.as_view(), name="admin-storefront-theme"),
    path("orders/", AdminOrderListView.as_view(), name="admin-order-list"),
    path("orders/<int:order_id>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
    path("", include(router.urls)),
    path("inventory/adjustments/", InventoryAdjustmentAdminView.as_view(), name="admin-inventory-adjustments"),
]
