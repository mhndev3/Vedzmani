"""Access boundaries for customer support tickets."""
import pytest

from apps.accounts.models import SupportTicket, SupportTicketMessage, User
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def test_customer_can_create_and_read_only_own_tickets(customer_client, make_staff, db):
    owner = User.objects.create_user("09123456789")
    other = User.objects.create_user("09123456780")
    owner_client = client_for(owner)
    response = owner_client.post(
        "/api/auth/support/tickets/",
        {"subject": "پیگیری سفارش", "category": "order", "message": "لطفاً وضعیت را بررسی کنید."},
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    ticket_id = response.json()["id"]
    assert owner_client.get(f"/api/auth/support/tickets/{ticket_id}/").status_code == 200
    assert client_for(other).get(f"/api/auth/support/tickets/{ticket_id}/").status_code == 404


def test_customer_cannot_read_internal_staff_notes(make_staff, db):
    customer = User.objects.create_user("09123456789")
    staff = make_staff("accounts.view_supportticket", "accounts.add_supportticketmessage")
    ticket = SupportTicket.objects.create(user=customer, subject="سؤال", category="other")
    SupportTicketMessage.objects.create(ticket=ticket, sender=staff, body="یادداشت محرمانه", is_internal=True)
    response = client_for(customer).get(f"/api/auth/support/tickets/{ticket.pk}/")
    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_staff_inbox_requires_explicit_permission(make_staff):
    assert client_for(make_staff()).get("/api/admin/support/tickets/").status_code == 403
    staff = make_staff("accounts.view_supportticket")
    assert client_for(staff).get("/api/admin/support/tickets/").status_code == 200


def test_staff_can_reply_and_update_ticket_but_permissions_are_separate(make_staff, db):
    customer = User.objects.create_user("09123456789")
    ticket = SupportTicket.objects.create(user=customer, subject="پیگیری", category="order")
    read_only = client_for(make_staff("accounts.view_supportticket"))
    assert read_only.patch(
        f"/api/admin/support/tickets/{ticket.pk}/", {"status": "resolved"}, content_type="application/json"
    ).status_code == 403
    staff = make_staff("accounts.view_supportticket", "accounts.change_supportticket", "accounts.add_supportticketmessage")
    client = client_for(staff)
    assert client.patch(
        f"/api/admin/support/tickets/{ticket.pk}/", {"status": "in_progress"}, content_type="application/json"
    ).status_code == 200
    response = client.post(
        f"/api/admin/support/tickets/{ticket.pk}/",
        {"message": "در حال بررسی است.", "is_internal": False},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert response.json()["messages"][-1]["body"] == "در حال بررسی است."


def test_staff_cannot_use_customer_ticket_endpoints(customer_client, make_staff):
    staff = make_staff("accounts.view_supportticket")
    assert client_for(staff).get("/api/auth/support/tickets/").status_code == 403
