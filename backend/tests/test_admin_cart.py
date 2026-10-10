"""Cart admin: inspection only, no PII leak in lists, nothing mutates stock/ownership."""

import pytest

from apps.accounts.models import User
from apps.cart.models import Cart, CartItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def cart_with_item(make_variant_size):
    user = User.objects.create_user("09123456789")
    vs = make_variant_size(stock=5)
    cart = Cart.objects.create(user=user)
    item = CartItem.objects.create(cart=cart, variant_size=vs, quantity=2)
    return cart, item, vs


def test_changelist_masks_owner_phone(su_client, cart_with_item):
    html = su_client.get("/admin/cart/cart/").content.decode()
    assert "+989123456789" not in html and "+9891****789" in html
    html = su_client.get("/admin/cart/cartitem/").content.decode()
    assert "+989123456789" not in html and "+9891****789" in html


def test_cart_detail_shows_contents_without_full_phone(su_client, cart_with_item):
    cart, item, vs = cart_with_item
    html = su_client.get(f"/admin/cart/cart/{cart.pk}/change/").content.decode()
    assert vs.sku in html and vs.variant.product.name in html
    assert "+989123456789" not in html
    assert su_client.get(f"/admin/cart/cartitem/{item.pk}/change/").status_code == 200


def test_cart_search_by_phone_fragment(su_client, cart_with_item):
    other = Cart.objects.create(user=User.objects.create_user("09120000000"))
    html = su_client.get("/admin/cart/cart/", {"q": "3456789"}).content.decode()
    assert "1 cart" in html and f"#{other.user_id} " not in html


def test_cart_and_items_cannot_be_created_or_edited_even_by_superuser(su_client, cart_with_item):
    cart, item, vs = cart_with_item
    assert su_client.get("/admin/cart/cart/add/").status_code == 403
    assert su_client.get("/admin/cart/cartitem/add/").status_code == 403
    assert su_client.post(f"/admin/cart/cart/{cart.pk}/change/", {"user": 999}).status_code == 403
    assert su_client.post(f"/admin/cart/cartitem/{item.pk}/change/", {"quantity": 9}).status_code == 403
    cart.refresh_from_db(), item.refresh_from_db(), vs.refresh_from_db()
    assert (cart.user.phone, item.quantity, vs.stock_quantity) == ("+989123456789", 2, 5)
