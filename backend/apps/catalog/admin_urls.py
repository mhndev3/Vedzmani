"""URL map for staff-only admin APIs; mounted under /api/admin/."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.orders.admin_api import AdminOrderDetailView, AdminOrderListView
from apps.accounts.admin_customers import AdminCustomerDetailView, AdminCustomerListView
from apps.accounts.admin_audit_api import AdminAuditEventListView
from apps.accounts.staff_admin_api import (
    AdminStaffListView, AdminStaffRoleAssignmentView,
    AdminStaffRoleDetailView, AdminStaffRoleListView,
)
from apps.accounts.support_api import AdminSupportTicketDetailView, AdminSupportTicketListView
from apps.orders.admin_shipping import ShippingMethodAdminViewSet
from .homepage_admin import HomepageSectionAdminViewSet
from .homepage_banner_admin import HomepageBannerAdminViewSet
from .homepage_banner_group_admin import HomepageBannerGroupAdminViewSet
from .admin_media_library import AdminMediaLibraryView
from .admin_product_variants import ProductWithVariantsCreateView
from .admin_product_workspace import ProductWorkspaceSaveView
from .storefront_theme import StorefrontThemeAdminView, StorefrontThemeRevisionView
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
router.register("shipping/methods", ShippingMethodAdminViewSet, basename="admin-shipping-method")
router.register("homepage/sections", HomepageSectionAdminViewSet, basename="admin-homepage-section")
router.register("homepage/banners", HomepageBannerAdminViewSet, basename="admin-homepage-banner")
router.register("homepage/banner-groups", HomepageBannerGroupAdminViewSet, basename="admin-homepage-banner-group")
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
    path("media/", AdminMediaLibraryView.as_view(), name="admin-media-library"),
    path("catalog/products/<int:product_id>/workspace-save/", ProductWorkspaceSaveView.as_view(), name="admin-product-workspace-save"),
    path("catalog/products/create-with-variants/", ProductWithVariantsCreateView.as_view(), name="admin-product-create-with-variants"),
    path("storefront/theme/", StorefrontThemeAdminView.as_view(), name="admin-storefront-theme"),
    path("storefront/theme/revisions/", StorefrontThemeRevisionView.as_view(), name="admin-storefront-theme-revisions"),
    path("audit-log/", AdminAuditEventListView.as_view(), name="admin-audit-log"),
    path("staff/", AdminStaffListView.as_view(), name="admin-staff-list"),
    path("staff/roles/", AdminStaffRoleListView.as_view(), name="admin-staff-role-list"),
    path("staff/roles/<int:role_id>/", AdminStaffRoleDetailView.as_view(), name="admin-staff-role-detail"),
    path("staff/<int:staff_id>/roles/", AdminStaffRoleAssignmentView.as_view(), name="admin-staff-role-assignment"),
    path("customers/", AdminCustomerListView.as_view(), name="admin-customer-list"),
    path("customers/<int:customer_id>/", AdminCustomerDetailView.as_view(), name="admin-customer-detail"),
    path("support/tickets/", AdminSupportTicketListView.as_view(), name="admin-support-ticket-list"),
    path("support/tickets/<int:ticket_id>/", AdminSupportTicketDetailView.as_view(), name="admin-support-ticket-detail"),
    path("orders/", AdminOrderListView.as_view(), name="admin-order-list"),
    path("orders/<int:order_id>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
    path("", include(router.urls)),
    path("inventory/adjustments/", InventoryAdjustmentAdminView.as_view(), name="admin-inventory-adjustments"),
]
