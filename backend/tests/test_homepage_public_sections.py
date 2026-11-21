from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
import pytest

from apps.catalog.models import Category, HomepageSection, Product


@pytest.mark.django_db
def test_public_homepage_exposes_only_published_sections():
    category = Category.objects.create(name="دورس", slug="sweatshirts")
    product = Product.objects.create(
        category=category, name="دورس تست", slug="test-sweatshirt",
        price=100000, is_active=True,
    )
    draft = HomepageSection.objects.create(title="پیش‌نویس", section_type=HomepageSection.TYPE_NEWEST_PRODUCTS)
    published = HomepageSection.objects.create(
        title="جدیدترین‌ها", section_type=HomepageSection.TYPE_NEWEST_PRODUCTS,
        status=HomepageSection.STATUS_PUBLISHED,
    )
    response = APIClient().get("/api/catalog/homepage-sections/")
    assert response.status_code == 200
    assert [item["id"] for item in response.data["sections"]] == [published.id]
    assert response.data["sections"][0]["title"] == "جدیدترین‌ها"
