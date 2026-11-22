"""Privacy and access boundaries for the read-only customer directory."""
from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.orders.models import Order
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def test_customer_directory_requires_staff_and_explicit_view_permission(customer_client, make_staff):
    assert customer_client.get("/api/admin/customers/").status_code in (401, 403)
    assert client_for(make_staff()).get("/api/admin/customers/").status_code == 403


def test_customer_directory_lists_only_customers_and_masks_phone(make_staff, db):
    customer = User.objects.create_user("09123456789")
    User.objects.create_user("09123456780", is_staff=True)
    User.objects.create_superuser("09123456781", password="S3cret-pass-1")
    client = client_for(make_staff("accounts.view_user"))
    response = client.get("/api/admin/customers/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["count"] == 1
    row = body["results"][0]
    assert row["id"] == customer.id
    assert row["phone_masked"] != customer.phone
    assert row["pii_hidden"] is True
    assert "phone" not in row
    assert "address" not in row
    assert "national_code" not in row


def test_customer_detail_contains_only_non_pii_summary(make_staff, db):
    customer = User.objects.create_user("09123456789")
    client = client_for(make_staff("accounts.view_user"))
    response = client.get(f"/api/admin/customers/{customer.pk}/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["id"] == customer.id
    assert body["phone_masked"].endswith("789")
    assert body["order_count"] == 0
    assert body["total_spent"] == "0"
    assert body["pii_hidden"] is True


def test_customer_directory_search_is_account_id_only(make_staff, db):
    customer = User.objects.create_user("09123456789")
    client = client_for(make_staff("accounts.view_user"))
    assert client.get(f"/api/admin/customers/?search={customer.pk}").json()["count"] == 1
    # A phone-shaped numeric string is treated only as an account ID, never as a phone lookup.
    response = client.get("/api/admin/customers/?search=09123456789")
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_customer_directory_filters_active_state(make_staff, db):
    User.objects.create_user("09123456789", is_active=True)
    User.objects.create_user("09123456780", is_active=False)
    client = client_for(make_staff("accounts.view_user"))
    assert client.get("/api/admin/customers/?active=true").json()["count"] == 1
    assert client.get("/api/admin/customers/?active=false").json()["count"] == 1


def test_customer_directory_has_no_mutation_methods(make_staff):
    client = client_for(make_staff("accounts.view_user"))
    assert client.post("/api/admin/customers/", {}, content_type="application/json").status_code == 405
    assert client.delete("/api/admin/customers/1/").status_code == 405


def test_customer_total_spent_includes_only_paid_orders(make_staff, db):
    customer = User.objects.create_user("09123456789")
    for status, amount in (
        (Order.PAID, "150000"),
        (Order.UNPAID, "300000"),
        (Order.FAILED, "500000"),
    ):
        Order.objects.create(
            user=customer,
            customer_phone=customer.phone,
            total=Decimal(amount),
            payment_status=status,
        )

    client = client_for(make_staff("accounts.view_user"))
    response = client.get(f"/api/admin/customers/{customer.pk}/")
    assert response.status_code == 200, response.content
    assert response.json()["order_count"] == 3
    assert response.json()["total_spent"] == "150000"
