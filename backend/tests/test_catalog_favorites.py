import pytest
from django.test import Client

from apps.catalog.models import Category, ColorVariant, Favorite, Product

pytestmark = pytest.mark.django_db


def make_product(active=True):
    category = Category.objects.create(name="پوشاک", slug="favorite-test")
    return Product.objects.create(category=category, product_code="FAV-01", name="محصول نشان‌شده", slug="favorite-product", price=100000, is_active=active)


def test_favorites_require_authentication():
    assert Client().get("/api/catalog/favorites/").status_code == 401


def test_customer_can_save_list_and_remove_own_favorite(api):
    product = make_product()
    variant = ColorVariant.objects.create(product=product, name="مشکی", slug="black", hex_color="#000000")
    api.login("09123456780")
    created = api.post("/api/catalog/favorites/", {"product_id": product.pk})
    assert created.status_code == 201
    assert created.json()["product_slug"] == product.slug
    assert Favorite.objects.filter(product=product).count() == 1
    assert api.post("/api/catalog/favorites/", {"product_id": product.pk}).status_code == 201
    assert Favorite.objects.filter(product=product).count() == 1

    listing = api.get("/api/catalog/favorites/")
    assert listing.status_code == 200
    favorite = listing.json()[0]
    assert favorite["product_id"] == product.pk
    assert favorite["card"]["variant_id"] == variant.pk
    assert favorite["card"]["slug"] == product.slug
    assert favorite["card"]["color"]["slug"] == "black"
    response = api.client.delete(f"/api/catalog/favorites/{product.slug}/", HTTP_X_CSRFTOKEN=api._token())
    assert response.status_code == 204
    assert Favorite.objects.count() == 0


def test_favorite_product_id_must_be_valid(api):
    api.login("09123456781")
    response = api.post("/api/catalog/favorites/", {"product_id": "not-an-id"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_inactive_products_are_not_favorited(api):
    product = make_product(active=False)
    api.login("09123456782")
    response = api.post("/api/catalog/favorites/", {"product_id": product.pk})
    assert response.status_code == 404
    assert Favorite.objects.count() == 0
