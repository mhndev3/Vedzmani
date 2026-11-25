import pytest
from django.test import Client

from apps.catalog.models import Category

pytestmark = pytest.mark.django_db


def test_homepage_category_selection_is_additive_and_ordered():
    Category.objects.create(
        name="دسته اصلی",
        slug="homepage-category-base",
        is_homepage_featured=True,
        homepage_position=5,
    )
    Category.objects.create(
        name="اکسسوری",
        slug="homepage-category-accessories",
        is_homepage_featured=True,
        homepage_position=6,
    )
    Category.objects.create(
        name="شلوار",
        slug="catalog-only-trousers",
        is_homepage_featured=False,
    )

    response = Client().get("/api/catalog/filters/")
    assert response.status_code == 200
    homepage_categories = response.json()["homepage_categories"]
    slugs = [item["slug"] for item in homepage_categories]
    assert slugs[:5] == ["sweatshirts", "knitwear", "jeans", "hoodies", "leather-jackets"]
    assert slugs[-2:] == ["homepage-category-base", "homepage-category-accessories"]
    assert "catalog-only-trousers" not in slugs
