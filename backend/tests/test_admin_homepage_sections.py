import pytest
from django.utils import timezone

from apps.catalog.models import Category, HomepageSection, Product
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def test_homepage_sections_require_staff_and_model_permissions(customer_client, make_staff):
    assert customer_client.get("/api/admin/homepage/sections/").status_code in (401, 403)
    assert client_for(make_staff()).get("/api/admin/homepage/sections/").status_code == 403


def test_homepage_section_crud_and_publish_timestamp(make_staff):
    category = Category.objects.create(name="لباس", slug="clothing")
    client = client_for(make_staff("catalog.add_homepagesection", "catalog.view_homepagesection", "catalog.change_homepagesection"))
    response = client.post("/api/admin/homepage/sections/", {
        "title": "دسته‌بندی‌های فروشگاه", "eyebrow": "انتخاب بر اساس سلیقه",
        "section_type": "categories", "status": "draft", "position": 0,
        "item_limit": 6, "categories": [category.pk], "products": [],
    }, content_type="application/json")
    assert response.status_code == 201, response.content
    section_id = response.json()["id"]
    assert response.json()["status"] == "draft"
    assert response.json()["categories"] == [category.pk]
    published = client.patch(f"/api/admin/homepage/sections/{section_id}/", {"status": "published"}, content_type="application/json")
    assert published.status_code == 200, published.content
    section = HomepageSection.objects.get(pk=section_id)
    assert section.status == "published"
    assert section.published_at is not None and section.published_at <= timezone.now()


def test_homepage_section_rejects_empty_or_mismatched_selection(make_staff):
    category = Category.objects.create(name="لباس", slug="clothing")
    client = client_for(make_staff("catalog.add_homepagesection", "catalog.view_homepagesection"))
    empty = client.post("/api/admin/homepage/sections/", {"title": "دسته‌بندی‌ها", "section_type": "categories", "categories": []}, content_type="application/json")
    assert empty.status_code == 400
    product = Product.objects.create(category=category, name="بافت", slug="knit", price="1000000", is_active=True)
    mismatch = client.post("/api/admin/homepage/sections/", {
        "title": "محصولات", "section_type": "products", "categories": [category.pk], "products": [product.pk],
    }, content_type="application/json")
    assert mismatch.status_code == 400


def test_homepage_section_cannot_select_inactive_products(make_staff):
    category = Category.objects.create(name="لباس", slug="clothing")
    product = Product.objects.create(category=category, name="پیش‌نویس", slug="draft-knit", price="1000000", is_active=False)
    client = client_for(make_staff("catalog.add_homepagesection", "catalog.view_homepagesection"))
    response = client.post("/api/admin/homepage/sections/", {
        "title": "محصولات", "section_type": "products", "products": [product.pk],
    }, content_type="application/json")
    assert response.status_code == 400
