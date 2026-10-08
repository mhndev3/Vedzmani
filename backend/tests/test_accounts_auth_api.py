import pytest
from django.contrib.sessions.models import Session
from django.test import Client

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

PHONE = "09123456789"


def test_new_phone_creates_user_and_session(api):
    response = api.login(PHONE)
    assert response.json()["is_new_user"] is True
    assert User.objects.count() == 1
    cookie = response.cookies["sessionid"]
    assert cookie["httponly"] and cookie["samesite"] == "Lax"
    assert Session.objects.count() == 1  # server-side session in PostgreSQL


def test_existing_phone_authenticates_the_existing_user(api):
    existing = User.objects.create_user("+989123456789")
    response = api.login("0912 345 6789")
    body = response.json()
    assert body["is_new_user"] is False and body["user"]["id"] == existing.pk
    assert User.objects.count() == 1


def test_me_returns_current_user(api):
    api.login(PHONE)
    response = api.get("/api/auth/me/")
    assert response.status_code == 200
    assert response.json() == {"id": User.objects.get().pk, "phone": "+989123456789", "is_staff": False}


def test_me_rejects_unauthenticated_requests(api):
    response = api.get("/api/auth/me/")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_logout_invalidates_the_session_server_side(api):
    api.login(PHONE)
    old_session_id = api.client.cookies["sessionid"].value
    assert api.post("/api/auth/logout/").status_code == 204
    assert api.get("/api/auth/me/").status_code == 401
    assert not Session.objects.filter(session_key=old_session_id).exists()

    stolen = Client()  # a client replaying the old cookie must not be logged in
    stolen.cookies["sessionid"] = old_session_id
    assert stolen.get("/api/auth/me/").status_code == 401


def test_logout_is_idempotent_for_anonymous_users(api):
    assert api.post("/api/auth/logout/").status_code == 204


def test_session_key_is_rotated_on_login(api):
    session = api.client.session  # pre-existing anonymous session (fixation attempt)
    session["seed"] = 1
    session.save()
    api.client.cookies["sessionid"] = session.session_key
    api.login(PHONE)
    assert api.client.cookies["sessionid"].value != session.session_key


def test_remember_me_false_uses_browser_session_cookie(api):
    api.login(PHONE)
    assert api.client.session.get_expire_at_browser_close() is True


def test_remember_me_true_sets_fixed_lifetime(api, settings):
    api.login(PHONE, remember_me=True)
    session = api.client.session
    assert session.get_expire_at_browser_close() is False
    assert abs(session.get_expiry_age() - settings.AUTH_REMEMBER_ME_SECONDS) < 5


def test_inactive_user_cannot_authenticate(api):
    User.objects.create_user("+989123456789", is_active=False)
    api.request_otp(PHONE)
    response = api.verify(api.last_code())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_disabled"
    assert api.get("/api/auth/me/").status_code == 401
