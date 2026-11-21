from django.urls import path

from . import views
from .homepage_public import HomepageSectionsPublicView
from .homepage_banner_public import HomepageBannersPublicView
from .storefront_theme import StorefrontThemePublicView

urlpatterns = [
    path("storefront/theme/", StorefrontThemePublicView.as_view(), name="storefront-theme-public"),
    path("homepage-sections/", HomepageSectionsPublicView.as_view(), name="catalog-homepage-sections"),
    path("homepage-banners/", HomepageBannersPublicView.as_view(), name="catalog-homepage-banners"),
    path("filters/", views.FilterOptionsView.as_view(), name="catalog-filter-options"),
    path("products/", views.ProductListView.as_view(), name="catalog-product-list"),
    path("variant-products/", views.VariantProductListView.as_view(), name="catalog-variant-product-list"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="catalog-product-detail"),
    path("favorites/", views.FavoriteListView.as_view(), name="catalog-favorite-list"),
    path("favorites/<slug:slug>/", views.FavoriteDetailView.as_view(), name="catalog-favorite-detail"),
]
