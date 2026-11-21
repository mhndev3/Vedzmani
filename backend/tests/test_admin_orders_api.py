"""Permission and PII boundaries for the custom read-only order workspace API."""
import pytest

from apps.accounts.models import User
from apps.accounts.phone import normalize_phone
from apps.orders import services
from tests.conftest import DELIVERY, ApiClient, client_for
from tests.test_cart_api import make_vs
from tests.test_orders_api import fill_cart

pytestmark = pytest.mark.django_db


def create_order():
    customer_client = ApiClient()
    customer_client.login("09120000991")
    customer = User.objects.get(phone=normalize_phone("09120000991"))
    fill_cart(customer, (make_vs(stock=5), 1))
    return services.create_order(customer, DELIVERY)


def test_order_workspace_requires_staff_and_explicit_view_permission(customer_client, make_staff):
    assert customer_client.get("/api/admin/orders/").status_code in (401, 403)
    assert client_for(make_staff()).get("/api/admin/orders/").status_code == 403


def test_order_workspace_masks_pii_without_dedicated_permission(make_staff):
    order = create_order()
    client = client_for(make_staff("orders.view_order"))
    response = client.get("/api/admin/orders/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["count"] == 1
    row = body["results"][0]
    assert row["id"] == order.id
    assert row["pii_hidden"] is True
    assert row["customer_phone"] != order.customer_phone
    assert row["recipient_name"] == ""
    assert row["address"] == ""
    assert row["items"][0]["sku"]


def test_order_workspace_shows_delivery_pii_only_with_explicit_permission(make_staff):
    order = create_order()
    client = client_for(make_staff("orders.view_order", "orders.view_order_pii"))
    response = client.get(f"/api/admin/orders/{order.pk}/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["pii_hidden"] is False
    assert body["customer_phone"] == order.customer_phone
    assert body["recipient_name"] == order.recipient_name
    assert body["postal_code"] == order.postal_code


def test_order_workspace_filters_status_and_rejects_unknown_status(make_staff):
    create_order()
    client = client_for(make_staff("orders.view_order"))
    assert client.get("/api/admin/orders/?status=pending").json()["count"] == 1
    assert client.get("/api/admin/orders/?status=shipped").status_code == 400


def test_order_workspace_has_no_mutation_methods(make_staff):
    client = client_for(make_staff("orders.view_order"))
    assert client.post("/api/admin/orders/", {}, content_type="application/json").status_code == 405
