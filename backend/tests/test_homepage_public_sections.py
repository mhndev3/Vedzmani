from rest_framework.test import APIClient
import pytest

from apps.catalog.models import Category, ColorVariant, HomepageSection, Product


@pytest.mark.django_db
def test_public_homepage_exposes_only_published_sections():
    HomepageSection.objects.create(title="پیش‌نویس", section_type=HomepageSection.TYPE_NEWEST_PRODUCTS)
    published = HomepageSection.objects.create(
        title="جدیدترین‌ها",
        section_type=HomepageSection.TYPE_NEWEST_PRODUCTS,
        status=HomepageSection.STATUS_PUBLISHED,
    )
    response = APIClient().get("/api/catalog/homepage-sections/")
    assert response.status_code == 200
    assert [item["id"] for item in response.data["sections"]] == [published.id]
    assert response.data["sections"][0]["title"] == "جدیدترین‌ها"


@pytest.mark.django_db
def test_newest_homepage_section_can_pin_selected_product_cards():
    category = Category.objects.create(name="بافت", slug="homepage-pinned-knitwear")
    pinned_product = Product.objects.create(
        category=category, name="محصول منتخب قدیمی", slug="homepage-pinned-old",
        price="1000000", is_active=True,
    )
    newest_product = Product.objects.create(
        category=category, name="محصول تازه", slug="homepage-pinned-new",
        price="1200000", is_active=True,
    )
    ColorVariant.objects.create(
        product=pinned_product, name="آبی", slug="blue", position=0,
    )
    ColorVariant.objects.create(
        product=newest_product, name="مشکی", slug="black", position=0,
    )
    section = HomepageSection.objects.create(
        title="جدیدترین‌ها با محصولات منتخب",
        section_type=HomepageSection.TYPE_NEWEST_PRODUCTS,
        status=HomepageSection.STATUS_PUBLISHED,
        item_limit=2,
    )
    section.products.add(pinned_product)

    response = APIClient().get("/api/catalog/homepage-sections/")
    assert response.status_code == 200
    row = response.data["sections"][0]
    assert row["product_ids"] == [pinned_product.pk]
    assert row["products"][0]["id"] == pinned_product.pk
    assert row["products"][1]["id"] == newest_product.pk
