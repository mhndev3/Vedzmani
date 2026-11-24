from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.catalog.models import HomepageBanner, HomepageBannerGroup
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
    empty_public = client.get("/api/catalog/homepage-banners/").json()
    assert empty_public == {"groups": [], "banners": []}

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
    assert "cta_url" in response.json()["error"]["details"]

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
    assert "ends_at" in response.json()["error"]["details"]


def test_banner_groups_can_be_created_and_render_as_independent_sliders(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    permissions = (
        "catalog.add_homepagebanner",
        "catalog.view_homepagebanner",
        "catalog.change_homepagebanner",
        "catalog.add_homepagebannergroup",
        "catalog.view_homepagebannergroup",
        "catalog.change_homepagebannergroup",
    )
    client = client_for(make_staff(*permissions))
    created_group = client.post(
        "/api/admin/homepage/banner-groups/",
        {"name": "پیشنهادهای ویژه", "slug": "special-offers", "position": 1, "is_active": True},
        content_type="application/json",
    )
    assert created_group.status_code == 201, created_group.content
    group_id = created_group.json()["id"]

    created_banner = client.post("/api/admin/homepage/banners/", {
        "group": group_id,
        "title": "تخفیف ویژه",
        "alt_text": "بنر تخفیف ویژه",
        "desktop_image": image_file("special.png"),
        "position": 0,
        "status": "published",
    })
    assert created_banner.status_code == 201, created_banner.content
    banner = HomepageBanner.objects.get(pk=created_banner.json()["id"])
    assert banner.group_id == group_id

    public = client.get("/api/catalog/homepage-banners/")
    assert public.status_code == 200
    assert [group["id"] for group in public.json()["groups"]] == [group_id]
    assert public.json()["groups"][0]["name"] == "پیشنهادهای ویژه"
    assert public.json()["groups"][0]["banners"][0]["id"] == banner.pk
    assert public.json()["banners"][0]["id"] == banner.pk

    disabled = client.patch(
        f"/api/admin/homepage/banner-groups/{group_id}/",
        {"is_active": False},
        content_type="application/json",
    )
    assert disabled.status_code == 200, disabled.content
    assert client.get("/api/catalog/homepage-banners/").json()["groups"] == []
    assert HomepageBanner.objects.filter(pk=banner.pk).exists()


def test_banner_revision_snapshot_keeps_its_group(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    group_a = HomepageBannerGroup.objects.get(slug="main")
    group_b = HomepageBannerGroup.objects.create(name="ویژه", slug="banner-revision-special")
    client = client_for(make_staff(
        "catalog.add_homepagebanner",
        "catalog.view_homepagebanner",
        "catalog.change_homepagebanner",
    ))
    created = client.post("/api/admin/homepage/banners/", {
        "group": group_a.pk,
        "title": "بنر",
        "alt_text": "تصویر بنر",
        "desktop_image": image_file("revision.png"),
        "status": "draft",
    })
    assert created.status_code == 201, created.content
    banner_id = created.json()["id"]

    changed = client.patch(
        f"/api/admin/homepage/banners/{banner_id}/",
        {"group": group_b.pk},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    history = client.get(f"/api/admin/homepage/banners/{banner_id}/revisions/")
    first_revision = history.json()[1]
    assert first_revision["snapshot"]["group"] == group_a.pk

    restored = client.post(
        f"/api/admin/homepage/banners/{banner_id}/revisions/",
        {"revision_id": first_revision["id"]},
        content_type="application/json",
    )
    assert restored.status_code == 200, restored.content
    assert HomepageBanner.objects.get(pk=banner_id).group_id == group_a.pk
