import pytest
from django.test import Client

from apps.orders.models import Order

pytestmark = pytest.mark.django_db


def test_order_creation_is_disabled_when_setting_is_off(api, settings):
    settings.ORDERS_ENABLED = False
    api.login("09123456783")
    response = api.post("/api/orders/", {
        "recipient_name": "Test",
        "province": "Tehran",
        "city": "Tehran",
        "address": "Example address",
        "postal_code": "1234567890",
    })
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "orders_disabled"
    assert Order.objects.count() == 0
