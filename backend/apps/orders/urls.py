from django.urls import path
from . import views

urlpatterns = [
    path("", views.OrderListCreateView.as_view(), name="order-list-create"),
    path("<int:order_id>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("<int:order_id>/payment/", views.SepPaymentInitiateView.as_view(), name="order-payment-initiate"),
    path("<int:order_id>/payment/torobpay/eligibility/", views.TorobPayEligibilityView.as_view(), name="torobpay-eligibility"),
    path("<int:order_id>/payment/torobpay/", views.TorobPayPaymentInitiateView.as_view(), name="torobpay-payment-initiate"),
    path("payment/sep/callback/", views.SepPaymentCallbackView.as_view(), name="sep-payment-callback"),
    path("payment/torobpay/callback/", views.TorobPayPaymentCallbackView.as_view(), name="torobpay-payment-callback"),
]
