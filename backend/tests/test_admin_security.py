"""Admin privilege boundaries: group permissions, staff accounts and phone-number search.

The user admin already stops non-superusers from editing `is_superuser`, groups and permissions. These tests pin the
other routes to the same outcome (stock `GroupAdmin`, password reset / `is_staff` of other staff accounts, and the
cart search that would unmask the phone digits the lists hide). Every authorization check is server-side: the tests
POST directly and never rely on a hidden button.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client

from apps.cart.models import Cart, CartItem
from tests.conftest import client_for, new_phone

User = get_user_model()

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Another-str0ng-pass"
PASSWORD_FORM = {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD}


def perm_id(label: str) -> int:
    app_label, codename = label.split(".")
    return Permission.objects.get(content_type__app_label=app_label, codename=codename).pk


def admin_login(phone: str, password: str = NEW_PASSWORD):
    return Client().post("/admin/login/?next=/admin/", {"username": phone, "password": password})


def fresh(user):
    """Reload without Django's per-instance permission cache."""
    return User.objects.get(pk=user.pk)


# --- groups: permissions can only be handed out by a superuser ------------------------------------------
def test_group_permissions_cannot_be_escalated_by_non_superusers(make_staff):
    staff = make_staff("auth.view_group", "auth.change_group")
    group = Group.objects.create(name="Order viewers")
    staff.groups.add(group)  # membership is assigned by a superuser; staff cannot edit their own groups
    grant = [perm_id("orders.view_order_pii"), perm_id("accounts.change_user")]

    response = client_for(staff).post(f"/admin/auth/group/{group.pk}/change/", {"name": group.name, "permissions": grant})

    assert response.status_code == 403
    assert not group.permissions.exists()
    assert not fresh(staff).has_perm("orders.view_order_pii")


def test_non_superusers_cannot_add_or_delete_groups(make_staff):
    staff = make_staff("auth.view_group", "auth.add_group", "auth.change_group", "auth.delete_group")
    group = Group.objects.create(name="Existing")
    client = client_for(staff)

    assert client.get("/admin/auth/group/add/").status_code == 403
    assert client.post("/admin/auth/group/add/", {"name": "Sneaky", "permissions": [perm_id("auth.add_group")]}).status_code == 403
    assert client.get(f"/admin/auth/group/{group.pk}/delete/").status_code == 403
    assert client.post(f"/admin/auth/group/{group.pk}/delete/", {"post": "yes"}).status_code == 403
    assert list(Group.objects.values_list("name", flat=True)) == ["Existing"]


def test_non_superusers_can_still_read_groups(make_staff):
    staff = make_staff("auth.view_group")
    group = Group.objects.create(name="Readable")
    client = client_for(staff)
    assert client.get("/admin/auth/group/").status_code == 200
    assert client.get(f"/admin/auth/group/{group.pk}/change/").status_code == 200


def test_superuser_can_still_manage_groups(su_client):
    response = su_client.post("/admin/auth/group/add/", {"name": "Order PII viewers", "permissions": [perm_id("orders.view_order_pii")]})
    assert response.status_code == 302
    group = Group.objects.get(name="Order PII viewers")
    assert list(group.permissions.values_list("codename", flat=True)) == ["view_order_pii"]

    response = su_client.post(f"/admin/auth/group/{group.pk}/change/", {"name": group.name, "permissions": []})
    assert response.status_code == 302 and not group.permissions.exists()


# --- user admin: staff accounts are managed by superusers only --------------------------------------------
def test_non_superuser_cannot_reset_a_staff_members_password(make_staff):
    manager = make_staff("accounts.view_user", "accounts.change_user")
    victim = make_staff("orders.view_order", "orders.view_order_pii")  # a staff member with more access
    client = client_for(manager)

    assert client.get(f"/admin/accounts/user/{victim.pk}/password/").status_code == 403
    assert client.post(f"/admin/accounts/user/{victim.pk}/password/", PASSWORD_FORM).status_code == 403

    victim = fresh(victim)
    assert not victim.has_usable_password() and not victim.check_password(NEW_PASSWORD)
    assert admin_login(victim.phone).status_code == 200  # form re-rendered with an error, no session


def test_non_superuser_cannot_edit_or_delete_a_staff_account(make_staff):
    manager = make_staff("accounts.view_user", "accounts.change_user", "accounts.delete_user")
    staff = make_staff("orders.view_order")
    client = client_for(manager)
    original = staff.phone

    assert client.post(f"/admin/accounts/user/{staff.pk}/change/", {"phone": "09129998877"}).status_code == 403
    assert client.get(f"/admin/accounts/user/{staff.pk}/delete/").status_code == 403
    assert client.post(f"/admin/accounts/user/{staff.pk}/delete/", {"post": "yes"}).status_code == 403

    staff = fresh(staff)
    assert staff.phone == original and staff.is_active and staff.is_staff


def test_non_superuser_cannot_turn_a_customer_into_staff(make_staff):
    manager = make_staff("accounts.view_user", "accounts.change_user")
    customer = User.objects.create_user(new_phone())
    client = client_for(manager)

    client.post(f"/admin/accounts/user/{customer.pk}/password/", PASSWORD_FORM)
    response = client.post(
        f"/admin/accounts/user/{customer.pk}/change/", {"phone": customer.phone, "is_active": "on", "is_staff": "on"}
    )

    assert response.status_code == 302  # the form saves; the read-only field is ignored
    customer = fresh(customer)
    assert not customer.is_staff
    assert admin_login(customer.phone).status_code == 200  # a customer can never enter the admin this way


def test_non_superuser_can_still_manage_customer_accounts(make_staff):
    manager = make_staff("accounts.view_user", "accounts.change_user")
    customer = User.objects.create_user(new_phone())

    response = client_for(manager).post(f"/admin/accounts/user/{customer.pk}/change/", {"phone": customer.phone})

    assert response.status_code == 302
    assert not fresh(customer).is_active  # deactivating a customer is a normal support action


def test_non_superuser_can_create_customers_but_not_staff(make_staff):
    manager = make_staff("accounts.view_user", "accounts.add_user", "accounts.change_user")  # Django's add view needs change too
    form = {"phone": "09121112233", "usable_password": "false", "is_staff": "on", "is_superuser": "on"}

    assert client_for(manager).post("/admin/accounts/user/add/", form).status_code == 302

    created = User.objects.get(phone="+989121112233")
    assert not created.is_staff and not created.is_superuser


def test_superuser_can_still_manage_staff_accounts(su_client, make_staff):
    staff = make_staff("orders.view_order")

    assert su_client.post(f"/admin/accounts/user/{staff.pk}/password/", PASSWORD_FORM).status_code == 302
    assert admin_login(staff.phone).status_code == 302
    response = su_client.post(
        f"/admin/accounts/user/{staff.pk}/change/", {"phone": staff.phone, "is_active": "on", "is_staff": "on"}
    )
    assert response.status_code == 302


def test_every_staff_member_can_still_change_their_own_password(make_staff):
    assert client_for(make_staff()).get("/admin/password_change/").status_code == 200


def test_full_phone_numbers_need_user_permissions_not_order_or_cart_ones(make_staff):
    customer = User.objects.create_user("09123456789")
    reader = client_for(make_staff("accounts.view_user"))
    assert "+989123456789" in reader.get("/admin/accounts/user/").content.decode()

    for perms in (("orders.view_order",), ("cart.view_cart",), ("inventory.view_inventoryadjustment",)):
        assert client_for(make_staff(*perms)).get(f"/admin/accounts/user/{customer.pk}/change/").status_code == 403


# --- cart admin: the masked owner phone must not be recoverable through search ----------------------------
@pytest.fixture
def two_carts(make_variant_size):
    """Owner A (+989123456789, shown as +9891****789; hidden digits 23456) and owner B (+989120000000)."""
    a = User.objects.create_user("09123456789")
    b = User.objects.create_user("09120000000")
    vs = make_variant_size(stock=5)
    for owner in (a, b):
        CartItem.objects.create(cart=Cart.objects.create(user=owner), variant_size=vs, quantity=1)
    return a, b, vs


def result_count(client, path, term):
    response = client.get(path, {"q": term})
    assert response.status_code == 200
    return response.context["cl"].result_count


def test_cart_search_does_not_reveal_masked_phone_digits(make_staff, two_carts):
    client = client_for(make_staff("cart.view_cart", "cart.view_cartitem"))
    # The hidden digits of owner A. If search used the phone, "23456" would narrow the list to one cart and
    # "99999" to none, which is exactly the oracle. The answers must be identical.
    assert result_count(client, "/admin/cart/cart/", "23456") == result_count(client, "/admin/cart/cart/", "99999") == 2
    assert result_count(client, "/admin/cart/cartitem/", "23456") == result_count(client, "/admin/cart/cartitem/", "99999") == 0


def test_cart_item_search_by_sku_and_product_still_works_without_phone_access(make_staff, two_carts):
    _, _, vs = two_carts
    client = client_for(make_staff("cart.view_cart", "cart.view_cartitem"))
    assert result_count(client, "/admin/cart/cartitem/", vs.sku) == 2
    assert result_count(client, "/admin/cart/cartitem/", vs.variant.product.name) == 2


@pytest.mark.parametrize("perm", ["accounts.view_user", "accounts.change_user"])
def test_cart_search_by_phone_is_allowed_for_staff_who_can_already_see_phones(make_staff, two_carts, perm):
    client = client_for(make_staff("cart.view_cart", "cart.view_cartitem", perm))
    assert result_count(client, "/admin/cart/cart/", "23456") == 1
    assert result_count(client, "/admin/cart/cart/", "99999") == 0
    assert result_count(client, "/admin/cart/cartitem/", "23456") == 1
    html = client.get("/admin/cart/cart/", {"q": "23456"}).content.decode()
    assert "+9891****789" in html and "+989123456789" not in html  # the column stays masked for everyone


def test_cart_search_by_phone_works_for_superusers(su_client, two_carts):
    assert result_count(su_client, "/admin/cart/cart/", "23456") == 1
    assert result_count(su_client, "/admin/cart/cartitem/", "23456") == 1


# --- bulk actions go through the same object-level checks ------------------------------------------------------
def test_bulk_delete_action_cannot_delete_staff_or_superuser_accounts(make_staff, superuser):
    manager = make_staff("accounts.view_user", "accounts.change_user", "accounts.delete_user")
    staff = make_staff("orders.view_order")
    customer = User.objects.create_user(new_phone())

    for protected in (staff, superuser):  # one at a time, so each protection is tested on its own
        response = client_for(manager).post(
            "/admin/accounts/user/",
            {"action": "delete_selected", "_selected_action": [protected.pk], "post": "yes"},
        )
        assert response.status_code in (200, 403)  # refused, never a silent delete
        assert User.objects.filter(pk=protected.pk).exists()
    # customers remain deletable through the same action
    client_for(manager).post(
        "/admin/accounts/user/", {"action": "delete_selected", "_selected_action": [customer.pk], "post": "yes"}
    )
    assert not User.objects.filter(pk=customer.pk).exists()


def test_bulk_delete_action_cannot_delete_groups_for_non_superusers(make_staff):
    staff = make_staff("auth.view_group", "auth.delete_group", "auth.change_group")
    group = Group.objects.create(name="Keep me")

    client_for(staff).post(
        "/admin/auth/group/", {"action": "delete_selected", "_selected_action": [group.pk], "post": "yes"}
    )

    assert Group.objects.filter(pk=group.pk).exists()
