from django.urls import path

from . import views

urlpatterns = [
    path("", views.OrderListCreateView.as_view(), name="order-list-create"),
    path("<int:order_id>/", views.OrderDetailView.as_view(), name="order-detail"),
]
