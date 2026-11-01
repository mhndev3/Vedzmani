from django.urls import path

from . import views

urlpatterns = [
    path("filters/", views.FilterOptionsView.as_view(), name="catalog-filter-options"),
    path("products/", views.ProductListView.as_view(), name="catalog-product-list"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="catalog-product-detail"),
    path("favorites/", views.FavoriteListView.as_view(), name="catalog-favorite-list"),
    path("favorites/<slug:slug>/", views.FavoriteDetailView.as_view(), name="catalog-favorite-detail"),
]
