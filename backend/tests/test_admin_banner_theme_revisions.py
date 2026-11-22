from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.catalog.models import HomepageBanner, HomepageBannerRevision, StorefrontTheme, StorefrontThemeRevision
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def banner_image(name="banner.png"):
    output = BytesIO()
    Image.new("RGB", (48, 24), (30, 50, 70)).save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


def test_homepage_banner_revision_history_and_rollback(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    client = client_for(make_staff(
        "catalog.add_homepagebanner",
        "catalog.view_homepagebanner",
        "catalog.change_homepagebanner",
    ))
    created = client.post("/api/admin/homepage/banners/", {
        "title": "نسخه اول",
        "alt_text": "تصویر بنر",
        "desktop_image": banner_image(),
        "status": "draft",
    })
    assert created.status_code == 201, created.content
    banner_id = created.json()["id"]

    updated = client.patch(
        f"/api/admin/homepage/banners/{banner_id}/",
        {"title": "نسخه دوم"},
        content_type="application/json",
    )
    assert updated.status_code == 200, updated.content

    history = client.get(f"/api/admin/homepage/banners/{banner_id}/revisions/")
    assert history.status_code == 200
    rows = history.json()
    assert [row["action"] for row in rows] == [
        HomepageBannerRevision.ACTION_UPDATED,
        HomepageBannerRevision.ACTION_CREATED,
    ]

    restored = client.post(
        f"/api/admin/homepage/banners/{banner_id}/revisions/",
        {"revision_id": rows[1]["id"]},
        content_type="application/json",
    )
    assert restored.status_code == 200, restored.content
    banner = HomepageBanner.objects.get(pk=banner_id)
    assert banner.title == "نسخه اول"
    assert banner.desktop_image.name
    assert banner.revisions.first().action == HomepageBannerRevision.ACTION_ROLLBACK


def test_homepage_banner_revision_permissions_are_separate(make_staff):
    banner = HomepageBanner.objects.create(
        title="بنر",
        alt_text="تصویر",
        desktop_image="homepage-banners/example.png",
    )
    read_only = client_for(make_staff("catalog.view_homepagebanner"))
    assert read_only.get(f"/api/admin/homepage/banners/{banner.pk}/revisions/").status_code == 200
    assert read_only.post(
        f"/api/admin/homepage/banners/{banner.pk}/revisions/",
        {"revision_id": 1},
        content_type="application/json",
    ).status_code == 403


def test_storefront_theme_revisions_record_publish_and_rollback(make_staff):
    actor = make_staff("catalog.view_storefronttheme", "catalog.change_storefronttheme")
    client = client_for(actor)
    baseline = client.get("/api/admin/storefront/theme/revisions/")
    assert baseline.status_code == 200
    original = baseline.json()[0]

    draft = {
        "primary": "#315b78",
        "primary_foreground": "#ffffff",
        "accent": "#dceaf2",
        "accent_foreground": "#18364b",
        "font": "system",
        "radius": "medium",
        "motion": "standard",
    }
    saved = client.patch(
        "/api/admin/storefront/theme/",
        {"settings": draft},
        content_type="application/json",
    )
    assert saved.status_code == 200, saved.content
    published = client.post(
        "/api/admin/storefront/theme/",
        {"action": "publish"},
        content_type="application/json",
    )
    assert published.status_code == 200, published.content

    history = client.get("/api/admin/storefront/theme/revisions/")
    assert history.status_code == 200
    assert history.json()[0]["action"] == StorefrontThemeRevision.ACTION_PUBLISHED

    restored = client.post(
        "/api/admin/storefront/theme/revisions/",
        {"revision_id": original["id"]},
        content_type="application/json",
    )
    assert restored.status_code == 200, restored.content
    theme = StorefrontTheme.objects.get(pk=1)
    assert theme.draft_settings == original["snapshot"]["draft_settings"]
    # Rollback restores the draft only. Public appearance remains unchanged until an explicit publish.
    assert theme.published_settings == draft
    assert theme.revisions.first().action == StorefrontThemeRevision.ACTION_ROLLBACK


def test_storefront_theme_revision_write_requires_change_permission(make_staff):
    read_only = client_for(make_staff("catalog.view_storefronttheme"))
    assert read_only.get("/api/admin/storefront/theme/revisions/").status_code == 200
    assert read_only.post(
        "/api/admin/storefront/theme/revisions/",
        {"revision_id": 1},
        content_type="application/json",
    ).status_code == 403
