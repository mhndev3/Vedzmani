from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.catalog.models import Category, ColorVariant, HomepageBanner, Product, VariantImage
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def banner_file():
    buffer = BytesIO()
    Image.new("RGB", (32, 18), (50, 70, 90)).save(buffer, format="PNG")
    return SimpleUploadedFile("banner.png", buffer.getvalue(), content_type="image/png")


def test_media_library_requires_staff_and_media_permissions(customer_client, make_staff):
    assert customer_client.get("/api/admin/media/").status_code in (401, 403)
    assert client_for(make_staff()).get("/api/admin/media/").status_code == 403


def test_media_library_lists_product_and_banner_media_with_source_links(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    category = Category.objects.create(name="لباس", slug="clothing")
    product = Product.objects.create(category=category, name="بافت آبی", slug="blue-knit", price=100000)
    variant = ColorVariant.objects.create(product=product, name="آبی", slug="blue")
    VariantImage.objects.create(
        variant=variant,
        storage_key="products/1/1/catalog.webp",
        alt_text="نمای جلوی بافت",
        width=640,
        height=800,
        file_size=12345,
    )
    banner = HomepageBanner.objects.create(
        title="بهاره",
        alt_text="بنر مجموعه بهاره",
        desktop_image=banner_file(),
    )
    client = client_for(make_staff("catalog.view_variantimage", "catalog.view_homepagebanner"))

    response = client.get("/api/admin/media/")
    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["count"] == 2
    product_row = next(row for row in payload["results"] if row["source"] == "product")
    banner_row = next(row for row in payload["results"] if row["source"] == "banner")
    assert product_row["title"] == "بافت آبی"
    assert product_row["owner_url"] == "/admin-panel/catalog"
    assert product_row["width"] == 640
    assert banner_row["source_id"] == banner.pk
    assert banner_row["owner_url"] == "/admin-panel/homepage/banners"
    assert banner_row["url"].endswith(banner.desktop_image.name)


def test_media_library_permission_filtering_and_search(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    category = Category.objects.create(name="لباس", slug="clothing")
    product = Product.objects.create(category=category, name="بافت زمستانی", slug="winter-knit", price=100000)
    variant = ColorVariant.objects.create(product=product, name="مشکی", slug="black")
    VariantImage.objects.create(
        variant=variant, storage_key="products/1/1/black.webp",
        alt_text="بافت مشکی", width=400, height=500,
    )
    HomepageBanner.objects.create(title="تابستان", alt_text="بنر تابستانی", desktop_image=banner_file())

    product_only = client_for(make_staff("catalog.view_variantimage"))
    all_rows = product_only.get("/api/admin/media/").json()
    assert all(row["source"] == "product" for row in all_rows["results"])
    assert product_only.get("/api/admin/media/?source=banner").json()["count"] == 0
    assert product_only.get("/api/admin/media/?q=زمستان").json()["count"] == 1
    assert product_only.get("/api/admin/media/?q=x").status_code == 400

    banner_only = client_for(make_staff("catalog.view_homepagebanner"))
    banners = banner_only.get("/api/admin/media/").json()
    assert banners["count"] == 1
    assert banners["results"][0]["source"] == "banner"


def test_media_library_rejects_unknown_source(make_staff):
    client = client_for(make_staff("catalog.view_variantimage"))
    assert client.get("/api/admin/media/?source=unknown").status_code == 400
