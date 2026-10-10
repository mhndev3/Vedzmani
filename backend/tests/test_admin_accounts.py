"""Admin access control + user admin (phone-based custom user)."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.accounts.models import OTPChallenge
from apps.cart.models import Cart
from tests.conftest import ADMIN_PASSWORD, client_for, new_phone

User = get_user_model()

pytestmark = pytest.mark.django_db

APP_LABELS = {"accounts", "catalog", "cart"}


def _our_models():
    return [m for m in admin.site._registry if m._meta.app_label in APP_LABELS]


# --- access control -----------------------------------------------------------
def test_anonymous_is_sent_to_admin_login():
    for url in ("/admin/", "/admin/catalog/product/", "/admin/accounts/user/"):
        response = Client().get(url)
        assert response.status_code == 302 and response["Location"].startswith("/admin/login/")


def test_customer_without_staff_flag_cannot_use_admin(customer_client):
    for url in ("/admin/", "/admin/catalog/product/", "/admin/accounts/user/", "/admin/cart/cart/"):
        response = customer_client.get(url)
        assert response.status_code == 302 and response["Location"].startswith("/admin/login/")


def test_staff_without_permissions_gets_403(make_staff):
    client = client_for(make_staff())
    for url in ("/admin/catalog/product/", "/admin/accounts/user/", "/admin/cart/cart/"):
        assert client.get(url).status_code == 403


def test_view_permission_does_not_grant_add_or_delete(make_staff, make_variant_size):
    product = make_variant_size().variant.product
    client = client_for(make_staff("catalog.view_product"))
    assert client.get("/admin/catalog/product/").status_code == 200
    assert client.get("/admin/catalog/product/add/").status_code == 403
    assert client.get(f"/admin/catalog/product/{product.pk}/delete/").status_code == 403


def test_every_registered_model_changelist_and_add_page_render(su_client):
    models = _our_models()
    assert {m.__name__ for m in models} >= {
        "User", "Category", "Collection", "Size", "Product", "ColorVariant", "VariantSize", "VariantImage",
        "Cart", "CartItem",
    }
    for model in models:
        opts = model._meta
        assert su_client.get(reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")).status_code == 200
        add = su_client.get(reverse(f"admin:{opts.app_label}_{opts.model_name}_add")).status_code
        assert add == (403 if opts.model_name in {"cart", "cartitem"} else 200), model


def test_otp_challenge_is_not_exposed_in_admin(su_client):
    assert OTPChallenge not in admin.site._registry
    assert su_client.get("/admin/accounts/otpchallenge/").status_code == 404


def test_staff_can_log_into_admin_with_phone_and_password(superuser):
    response = Client().post("/admin/login/?next=/admin/", {"username": superuser.phone, "password": ADMIN_PASSWORD})
    assert response.status_code == 302 and response["Location"] == "/admin/"


def test_non_staff_with_password_cannot_log_into_admin():
    user = User.objects.create_user(new_phone(), password=ADMIN_PASSWORD)
    response = Client().post("/admin/login/", {"username": user.phone, "password": ADMIN_PASSWORD})
    assert response.status_code == 200  # form re-rendered with an error, no session


# --- user admin ---------------------------------------------------------------
def _add_data(phone, password="Str0ng-pass-xyz", usable="true"):
    return {"phone": phone, "usable_password": usable, "password1": password, "password2": password}


def test_add_user_normalizes_phone_and_hashes_password(su_client):
    response = su_client.post("/admin/accounts/user/add/", _add_data("0912 111 2233"))
    assert response.status_code == 302
    user = User.objects.get(phone="+989121112233")
    assert user.check_password("Str0ng-pass-xyz") and not user.is_staff and not user.is_superuser


def test_add_user_without_password_is_otp_only(su_client):
    response = su_client.post("/admin/accounts/user/add/", {"phone": "09121112233", "usable_password": "false"})
    assert response.status_code == 302
    assert not User.objects.get(phone="+989121112233").has_usable_password()


def test_add_user_rejects_duplicate_spelling_and_invalid_phone(su_client):
    User.objects.create_user("09121112233")
    dup = su_client.post("/admin/accounts/user/add/", _add_data("+98 912 111 2233"))
    assert dup.status_code == 200 and b"already exists" in dup.content
    assert su_client.post("/admin/accounts/user/add/", _add_data("12345")).status_code == 200
    assert User.objects.count() == 2  # existing user + the superuser fixture


def test_change_page_never_renders_password_hash(su_client):
    user = User.objects.create_user(new_phone(), password="Another-pass-9")
    html = su_client.get(f"/admin/accounts/user/{user.pk}/change/").content.decode()
    assert user.password not in html and "md5$" not in html
    assert "change password" in html


def test_superuser_can_edit_flags(su_client):
    user = User.objects.create_user(new_phone())
    response = su_client.post(
        f"/admin/accounts/user/{user.pk}/change/", {"phone": user.phone, "is_active": "on", "is_staff": "on"}
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.is_staff and not user.is_superuser


def test_non_superuser_cannot_grant_superuser_or_touch_superusers(make_staff, superuser):
    manager = make_staff("accounts.view_user", "accounts.change_user")
    client = client_for(manager)
    target = User.objects.create_user(new_phone())
    response = client.post(
        f"/admin/accounts/user/{target.pk}/change/",
        {"phone": target.phone, "is_active": "on", "is_superuser": "on"},
    )
    assert response.status_code == 302
    target.refresh_from_db()
    assert not target.is_superuser  # field is read-only for non-superusers
    # a superuser's record is view-only for them: no edits, no password reset, no delete
    url = f"/admin/accounts/user/{superuser.pk}/"
    assert client.post(url + "change/", {"phone": "09129999999", "is_active": "on"}).status_code == 403
    assert client.get(url + "password/").status_code == 403
    assert client.get(url + "delete/").status_code == 403
    superuser.refresh_from_db()
    assert superuser.phone != "+989129999999"


def test_search_accepts_any_phone_spelling(su_client):
    User.objects.create_user("09123456789")
    html = su_client.get("/admin/accounts/user/", {"q": "0912 345 6789"}).content.decode()
    assert "+989123456789" in html


def test_deleting_a_user_with_a_cart_is_not_blocked_by_cart_admin(su_client):
    user = User.objects.create_user(new_phone())
    Cart.objects.create(user=user)
    response = su_client.post(f"/admin/accounts/user/{user.pk}/delete/", {"post": "yes"})
    assert response.status_code == 302
    assert not User.objects.filter(pk=user.pk).exists()
