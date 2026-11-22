"""Security and audit tests for superuser-only staff role management."""
import pytest
from django.contrib.auth.models import Group, Permission

from apps.accounts.authentication import OTP_SESSION_FLAG
from apps.accounts.models import AdminAuditEvent, User
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def test_staff_role_management_is_superuser_only(make_staff, superuser):
    assert client_for(make_staff()).get("/api/admin/staff/roles/").status_code == 403
    assert client_for(superuser).get("/api/admin/staff/roles/").status_code == 200


def test_otp_established_superuser_session_cannot_manage_staff(superuser):
    client = client_for(superuser)
    session = client.session
    session[OTP_SESSION_FLAG] = True
    session.save()
    assert client.get("/api/admin/staff/roles/").status_code == 403


def test_role_creation_only_accepts_curated_permissions_and_audits_change(superuser):
    client = client_for(superuser)
    response = client.post(
        "/api/admin/staff/roles/",
        {"name": "مدیر کاتالوگ", "permissions": ["catalog.view_product", "catalog.change_product"]},
        content_type="application/json",
    )
    assert response.status_code == 201
    role = Group.objects.get(name="مدیر کاتالوگ")
    assert set(role.permissions.values_list("codename", flat=True)) == {"view_product", "change_product"}

    event = AdminAuditEvent.objects.get(entity_type="staff_role", entity_id=role.pk)
    assert event.actor == superuser
    assert event.details["before"] == {}
    assert event.details["after"]["name"] == role.name
    assert set(event.details["after"]["permissions"]) == {"catalog.view_product", "catalog.change_product"}
    assert AdminAuditEvent.objects.filter(path="/api/admin/staff/roles/").count() == 1


def test_role_api_rejects_privileged_or_unmanaged_permissions(superuser):
    client = client_for(superuser)
    for permission in ("auth.change_group", "accounts.change_user", "orders.change_order"):
        response = client.post(
            "/api/admin/staff/roles/",
            {"name": f"invalid-{permission}", "permissions": [permission]},
            content_type="application/json",
        )
        assert response.status_code == 400
    assert Group.objects.count() == 0


def test_role_update_records_before_and_after_permission_snapshots(superuser):
    role = Group.objects.create(name="پشتیبانی")
    role.permissions.add(Permission.objects.get(content_type__app_label="accounts", codename="view_supportticket"))
    client = client_for(superuser)
    response = client.patch(
        f"/api/admin/staff/roles/{role.pk}/",
        {"name": "سرپرست پشتیبانی", "permissions": ["accounts.view_supportticket", "accounts.change_supportticket"]},
        content_type="application/json",
    )
    assert response.status_code == 200
    event = AdminAuditEvent.objects.get(entity_type="staff_role", entity_id=role.pk)
    assert event.details["before"]["name"] == "پشتیبانی"
    assert event.details["after"]["name"] == "سرپرست پشتیبانی"
    assert event.details["before"]["permissions"] == ["accounts.view_supportticket"]
    assert event.details["after"]["permissions"] == ["accounts.change_supportticket", "accounts.view_supportticket"]


def test_staff_role_assignment_is_audited_and_does_not_expose_phone(make_staff, superuser):
    staff = make_staff()
    previous = Group.objects.create(name="اپراتور قبلی")
    next_role = Group.objects.create(name="مدیر کاتالوگ")
    previous.permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_category"))
    next_role.permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_product"))
    staff.groups.add(previous)

    client = client_for(superuser)
    listed = client.get("/api/admin/staff/")
    assert listed.status_code == 200
    staff_payload = next(row for row in listed.json()["results"] if row["id"] == staff.pk)
    assert "phone" not in staff_payload
    assert staff_payload["roles"] == [{"id": previous.pk, "name": previous.name}]

    response = client.patch(
        f"/api/admin/staff/{staff.pk}/roles/",
        {"role_ids": [next_role.pk]},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert list(staff.groups.values_list("pk", flat=True)) == [next_role.pk]
    event = AdminAuditEvent.objects.get(entity_type="staff_user_roles", entity_id=staff.pk)
    assert event.details["before"] == [{"id": previous.pk, "name": previous.name}]
    assert event.details["after"] == [{"id": next_role.pk, "name": next_role.name}]
    assert AdminAuditEvent.objects.filter(path=f"/api/admin/staff/{staff.pk}/roles/").count() == 1


def test_staff_role_assignment_rejects_customer_superuser_and_unmanaged_role(make_staff, superuser, db):
    client = client_for(superuser)
    customer = User.objects.create_user("09123456789")
    other_superuser = User.objects.create_superuser("09123456788", password="Strong-password-123")
    unsafe = Group.objects.create(name="نقش ناامن")
    unsafe.permissions.add(Permission.objects.get(content_type__app_label="auth", codename="change_group"))

    for user in (customer, other_superuser):
        response = client.patch(
            f"/api/admin/staff/{user.pk}/roles/",
            {"role_ids": []},
            content_type="application/json",
        )
        assert response.status_code == 404

    response = client.patch(
        f"/api/admin/staff/{make_staff().pk}/roles/",
        {"role_ids": [unsafe.pk]},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_role_cannot_be_deleted_while_assigned(make_staff, superuser):
    role = Group.objects.create(name="نقش در حال استفاده")
    staff = make_staff()
    staff.groups.add(role)
    response = client_for(superuser).delete(f"/api/admin/staff/roles/{role.pk}/")
    assert response.status_code == 409
    assert Group.objects.filter(pk=role.pk).exists()


def test_audit_feed_returns_safe_before_after_details(make_staff, superuser):
    AdminAuditEvent.objects.create(
        actor=superuser, action="patch", method="PATCH", path="/api/admin/staff/4/roles/",
        entity_type="staff_user_roles", entity_id=4, response_status=200,
        details={"before": [{"id": 1, "name": "پشتیبانی"}], "after": [{"id": 2, "name": "کاتالوگ"}]},
    )
    response = client_for(make_staff("accounts.view_adminauditevent")).get("/api/admin/audit-log/")
    assert response.status_code == 200
    assert response.json()["results"][0]["details"]["before"][0]["name"] == "پشتیبانی"



def test_assignment_preserves_groups_outside_workspace_allowlist(make_staff, superuser):
    staff = make_staff()
    external = Group.objects.create(name="External security group")
    external.permissions.add(Permission.objects.get(content_type__app_label="auth", codename="change_group"))
    workspace_role = Group.objects.create(name="Catalog viewer")
    workspace_role.permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_product"))

    response = client_for(superuser).patch(
        f"/api/admin/staff/{staff.pk}/roles/",
        {"role_ids": [workspace_role.pk]},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert set(staff.groups.values_list("pk", flat=True)) == {external.pk, workspace_role.pk}
    assert response.json()["unmanaged_role_count"] == 1


def test_unmanaged_role_cannot_be_deleted_through_workspace(superuser):
    unsafe = Group.objects.create(name="External security group")
    unsafe.permissions.add(Permission.objects.get(content_type__app_label="auth", codename="change_group"))
    response = client_for(superuser).delete(f"/api/admin/staff/roles/{unsafe.pk}/")
    assert response.status_code == 409
    assert Group.objects.filter(pk=unsafe.pk).exists()
