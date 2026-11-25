import pytest
from django.test import Client

from apps.catalog.models import Category

pytestmark = pytest.mark.django_db


def test_homepage_category_selection_is_additive_and_ordered():
    Category.objects.create(
        name="دسته اصلی",
        slug="homepage-category-base",
        is_homepage_featured=True,
        homepage_position=0,
    )
    Category.objects.create(
        name="اکسسوری",
        slug="homepage-category-accessories",
        is_homepage_featured=True,
        homepage_position=5,
    )
    Category.objects.create(
        name="شلوار",
        slug="catalog-only-trousers",
        is_homepage_featured=False,
    )

    response = Client().get("/api/catalog/filters/")
    assert response.status_code == 200
    homepage_categories = response.json()["homepage_categories"]
    assert [item["slug"] for item in homepage_categories] == [
        "homepage-category-base",
        "homepage-category-accessories",
    ]
    assert all(item["slug"] != "catalog-only-trousers" for item in homepage_categories)
