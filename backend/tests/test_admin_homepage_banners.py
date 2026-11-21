from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.catalog.models import HomepageBanner
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def image_file(name="banner.png", color=(20, 30, 40)):
    buffer = BytesIO()
    Image.new("RGB", (64, 32), color).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def test_homepage_banner_admin_requires_staff_and_model_permission(customer_client, make_staff):
    assert customer_client.get("/api/admin/homepage/banners/").status_code in (401, 403)
    assert client_for(make_staff()).get("/api/admin/homepage/banners/").status_code == 403


def test_homepage_banner_draft_publish_and_public_visibility(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client = client_for(make_staff(
        "catalog.add_homepagebanner",
        "catalog.view_homepagebanner",
        "catalog.change_homepagebanner",
    ))
    response = client.post("/api/admin/homepage/banners/", {
        "title": "تابستان",
        "alt_text": "بنر مجموعه تابستانی ودزمانی",
        "desktop_image": image_file(),
        "cta_label": "مشاهده محصولات",
        "cta_url": "/products",
        "position": 0,
        "status": "draft",
    })
    assert response.status_code == 201, response.content
    banner_id = response.json()["id"]
    assert client.get("/api/catalog/homepage-banners/").json() == {"banners": []}

    published = client.patch(
        f"/api/admin/homepage/banners/{banner_id}/",
        data='{"status":"published"}',
        content_type="application/json",
    )
    assert published.status_code == 200, published.content
    banner = HomepageBanner.objects.get(pk=banner_id)
    assert banner.published_at is not None
    public = client.get("/api/catalog/homepage-banners/")
    assert public.status_code == 200
    assert len(public.json()["banners"]) == 1
    assert public.json()["banners"][0]["cta_url"] == "/products"


def test_homepage_banner_rejects_external_cta_and_invalid_schedule(make_staff):
    client = client_for(make_staff("catalog.add_homepagebanner", "catalog.view_homepagebanner"))
    response = client.post("/api/admin/homepage/banners/", {
        "title": "بنر",
        "alt_text": "متن جایگزین",
        "desktop_image": image_file(),
        "cta_url": "https://example.com",
    })
    assert response.status_code == 400
    assert "cta_url" in response.json()

    start = timezone.now()
    end = start - timedelta(minutes=1)
    response = client.post("/api/admin/homepage/banners/", {
        "title": "بنر",
        "alt_text": "متن جایگزین",
        "desktop_image": image_file("second.png"),
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
    })
    assert response.status_code == 400
    assert "ends_at" in response.json()
