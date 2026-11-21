from django.contrib import admin
from django.urls import include, path

from apps.orders.views import SepPaymentCallbackView

handler404 = "apps.core.views.api_not_found"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/admin/", include("apps.catalog.admin_urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/cart/", include("apps.cart.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("sep/cb/", SepPaymentCallbackView.as_view(), name="sep-payment-callback-short"),
    path("api/", include("apps.core.urls")),
]
