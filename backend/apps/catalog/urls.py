from django.urls import path

from . import views

urlpatterns = [
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="catalog-product-detail"),
]
