from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.csrf, name="auth-csrf"),
    path("otp/request/", views.OTPRequestView.as_view(), name="auth-otp-request"),
    path("otp/verify/", views.OTPVerifyView.as_view(), name="auth-otp-verify"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
]
