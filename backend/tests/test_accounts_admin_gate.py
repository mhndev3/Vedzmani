"""Django admin must be entered with the staff password, never with an OTP-only session.

ADMIN.md: staff sign in with phone + password at /admin/login/. The customer OTP flow creates a normal Django
session; without a gate that session would also open /admin/ for any is_staff phone, so possession of an SMS
code (SIM swap, provider compromise, interception) would equal admin access."""

import pytest
from django.test import Client

from apps.accounts.models import User
from tests.conftest import ADMIN_PASSWORD, client_for, new_phone

pytestmark = pytest.mark.django_db

ADMIN_PAGES = ["/admin/", "/admin/accounts/user/"]


def is_admin_login_redirect(response):
    return response.status_code == 302 and "/admin/login/" in response["Location"]


def admin_password_login(client, phone, password):
    client.get("/admin/login/")  # sets the csrftoken cookie
    token = client.cookies["csrftoken"].value
    return client.post(
        "/admin/login/",
        {"username": phone, "password": password, "next": "/admin/"},
        HTTP_X_CSRFTOKEN=token,
    )


@pytest.fixture
def superuser_phone(superuser):
    return superuser.phone


# ------------------------------------------------------------------ bypass --
@pytest.mark.parametrize("page", ADMIN_PAGES)
def test_otp_session_of_a_superuser_does_not_open_the_admin(api, superuser_phone, page):
    api.login(superuser_phone)
    assert api.get("/api/auth/me/").json()["is_staff"] is True  # the customer API still works for staff
    assert is_admin_login_redirect(api.get(page))


@pytest.mark.parametrize("page", ADMIN_PAGES)
def test_otp_session_of_staff_without_a_password_does_not_open_the_admin(api, make_staff, page):
    staff = make_staff("accounts.view_user")
    assert not staff.has_usable_password()
    api.login(staff.phone)
    assert is_admin_login_redirect(api.get(page))


def test_otp_session_of_a_customer_still_cannot_open_the_admin(api):
    api.login("09129990001")
    assert is_admin_login_redirect(api.get("/admin/"))


def test_admin_post_with_an_otp_session_is_refused_not_executed(api, superuser_phone):
    target = User.objects.create_user(new_phone())
    api.login(superuser_phone)
    token = api.client.cookies["csrftoken"].value
    response = api.client.post(
        f"/admin/accounts/user/{target.pk}/delete/", {"post": "yes"}, HTTP_X_CSRFTOKEN=token
    )
    assert is_admin_login_redirect(response)
    assert User.objects.filter(pk=target.pk).exists()


# ------------------------------------------------------- password login ok --
@pytest.mark.parametrize("page", ADMIN_PAGES)
def test_password_login_opens_the_admin(superuser_phone, page):
    client = Client(enforce_csrf_checks=True)
    response = admin_password_login(client, superuser_phone, ADMIN_PASSWORD)
    assert response.status_code == 302 and response["Location"] == "/admin/"
    assert client.get(page).status_code == 200


def test_password_login_after_an_otp_login_lifts_the_gate(api, superuser_phone):
    api.login(superuser_phone)
    assert is_admin_login_redirect(api.get("/admin/"))
    response = admin_password_login(api.client, superuser_phone, ADMIN_PASSWORD)
    assert response.status_code == 302 and response["Location"] == "/admin/"
    assert api.get("/admin/").status_code == 200
    assert api.get("/api/auth/me/").status_code == 200  # same session still serves the customer API


def test_wrong_password_does_not_lift_the_gate(api, superuser_phone):
    api.login(superuser_phone)
    response = admin_password_login(api.client, superuser_phone, "definitely-wrong")
    assert response.status_code == 200  # the login form is shown again with an error
    assert is_admin_login_redirect(api.get("/admin/"))


def test_a_later_otp_login_closes_the_admin_again(api, superuser_phone):
    assert admin_password_login(api.client, superuser_phone, ADMIN_PASSWORD).status_code == 302
    assert api.get("/admin/").status_code == 200
    api.login(superuser_phone)  # the session is now (also) established through an SMS code
    assert is_admin_login_redirect(api.get("/admin/"))


# ------------------------------------------------------ nothing else moves --
def test_logout_closes_the_admin(api, superuser_phone):
    admin_password_login(api.client, superuser_phone, ADMIN_PASSWORD)
    assert api.post("/api/auth/logout/").status_code == 204
    assert is_admin_login_redirect(api.get("/admin/"))


def test_sessions_created_without_the_otp_flow_are_unaffected(superuser, make_staff):
    """The admin test-suite (and the e2e helper) create sessions with force_login: they carry no OTP marker."""
    assert client_for(superuser).get("/admin/").status_code == 200
    staff = make_staff("accounts.view_user")
    assert client_for(staff).get("/admin/accounts/user/").status_code == 200
