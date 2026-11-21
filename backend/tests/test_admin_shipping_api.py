"""Security and validation tests for shipping method administration."""
import pytest

from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def test_shipping_methods_require_staff_and_explicit_model_permissions(customer_client, make_staff):
    assert customer_client.get("/api/admin/shipping/methods/").status_code in (401, 403)
    assert client_for(make_staff()).get("/api/admin/shipping/methods/").status_code == 403


def test_shipping_method_quote_and_fixed_tariffs(make_staff):
    client = client_for(make_staff("orders.view_shippingmethod", "orders.add_shippingmethod", "orders.change_shippingmethod"))

    quote = client.post("/api/admin/shipping/methods/", {
        "code": "post-quote",
        "name": "پست",
        "provider": "post",
        "pricing_mode": "quote",
        "amount_toman": None,
        "is_active": False,
    }, content_type="application/json")
    assert quote.status_code == 201, quote.content
    assert quote.json()["amount_toman"] is None

    fixed = client.post("/api/admin/shipping/methods/", {
        "code": "tipax-fixed",
        "name": "تیپاکس",
        "provider": "tipax",
        "pricing_mode": "fixed",
        "amount_toman": 85000,
        "min_delivery_days": 1,
        "max_delivery_days": 3,
        "is_active": False,
    }, content_type="application/json")
    assert fixed.status_code == 201, fixed.content
    assert fixed.json()["amount_toman"] == 85000


def test_shipping_method_rejects_inconsistent_rates_and_delivery_windows(make_staff):
    client = client_for(make_staff("orders.view_shippingmethod", "orders.add_shippingmethod"))
    missing_amount = client.post("/api/admin/shipping/methods/", {
        "code": "bad-fixed", "name": "تعرفه ثابت", "pricing_mode": "fixed",
    }, content_type="application/json")
    assert missing_amount.status_code == 400

    quote_with_amount = client.post("/api/admin/shipping/methods/", {
        "code": "bad-quote", "name": "استعلام", "pricing_mode": "quote", "amount_toman": 1000,
    }, content_type="application/json")
    assert quote_with_amount.status_code == 400

    invalid_days = client.post("/api/admin/shipping/methods/", {
        "code": "bad-days", "name": "ارسال", "min_delivery_days": 5, "max_delivery_days": 2,
    }, content_type="application/json")
    assert invalid_days.status_code == 400


def test_shipping_methods_can_be_deactivated_but_not_deleted(make_staff):
    client = client_for(make_staff("orders.view_shippingmethod", "orders.add_shippingmethod", "orders.change_shippingmethod"))
    created = client.post("/api/admin/shipping/methods/", {
        "code": "local-courier", "name": "پیک", "pricing_mode": "quote", "is_active": True,
    }, content_type="application/json")
    assert created.status_code == 201, created.content

    updated = client.patch(f"/api/admin/shipping/methods/{created.json()['id']}/", {
        "is_active": False,
    }, content_type="application/json")
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert client.delete(f"/api/admin/shipping/methods/{created.json()['id']}/").status_code == 405
