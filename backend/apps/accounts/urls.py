from django.urls import path

from . import views
from .support_api import CustomerSupportTicketDetailView, CustomerSupportTicketListView

urlpatterns = [
    path("csrf/", views.csrf, name="auth-csrf"),
    path("password/login/", views.PasswordLoginView.as_view(), name="auth-password-login"),
    path("password/set/", views.SetPasswordView.as_view(), name="auth-password-set"),
    path("otp/request/", views.OTPRequestView.as_view(), name="auth-otp-request"),
    path("otp/verify/", views.OTPVerifyView.as_view(), name="auth-otp-verify"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("profile/", views.ProfileView.as_view(), name="auth-profile"),
    path("support/tickets/", CustomerSupportTicketListView.as_view(), name="customer-support-ticket-list"),
    path("support/tickets/<int:ticket_id>/", CustomerSupportTicketDetailView.as_view(), name="customer-support-ticket-detail"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
]
