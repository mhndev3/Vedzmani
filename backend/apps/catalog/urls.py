from django.urls import path

from . import views

urlpatterns = [
    path("filters/", views.FilterOptionsView.as_view(), name="catalog-filter-options"),
    path("products/", views.ProductListView.as_view(), name="catalog-product-list"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="catalog-product-detail"),
]
