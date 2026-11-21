"""Privacy and authorization tests for the admin audit trail."""
import pytest

from apps.accounts.models import AdminAuditEvent, User
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def test_staff_mutation_is_audited_without_request_payload(make_staff):
    staff = make_staff("accounts.view_adminauditevent", "catalog.add_category")
    client = client_for(staff)
    response = client.post("/api/admin/catalog/categories/", {"name": "آزمایشی", "description": "محرمانه"}, content_type="application/json")
    event = AdminAuditEvent.objects.filter(actor=staff, path="/api/admin/catalog/categories/").latest("id")
    assert event.method == "POST"
    assert event.response_status == response.status_code
    assert "آزمایشی" not in event.path
    assert not hasattr(event, "request_body")


def test_audit_feed_requires_explicit_permission(make_staff):
    assert client_for(make_staff()).get("/api/admin/audit-log/").status_code == 403
    assert client_for(make_staff("accounts.view_adminauditevent")).get("/api/admin/audit-log/").status_code == 200


def test_audit_feed_is_read_only_and_paginated(make_staff):
    staff = make_staff("accounts.view_adminauditevent")
    for index in range(3):
        AdminAuditEvent.objects.create(actor=staff, action="patch", method="PATCH", path=f"/api/admin/catalog/products/{index + 1}/", entity_type="products", entity_id=index + 1, response_status=200)
    client = client_for(staff)
    result = client.get("/api/admin/audit-log/?page=1")
    assert result.status_code == 200 and result.json()["count"] == 3
    assert len(result.json()["results"]) == 3
    assert client.post("/api/admin/audit-log/", {}, content_type="application/json").status_code == 405


def test_customer_cannot_view_audit_feed(db):
    customer = User.objects.create_user("09123456789")
    assert client_for(customer).get("/api/admin/audit-log/").status_code == 403
