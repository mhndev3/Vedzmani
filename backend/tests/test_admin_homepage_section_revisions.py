import pytest

from apps.catalog.models import HomepageSection, HomepageSectionRevision
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def test_homepage_section_revisions_capture_updates_and_support_rollback(make_staff):
    actor = make_staff(
        "catalog.add_homepagesection",
        "catalog.view_homepagesection",
        "catalog.change_homepagesection",
    )
    client = client_for(actor)
    created = client.post(
        "/api/admin/homepage/sections/",
        {
            "title": "جدیدترین‌ها",
            "eyebrow": "ویترین",
            "section_type": "newest_products",
            "status": "draft",
            "position": 0,
            "item_limit": 8,
            "show_view_all": True,
            "view_all_url": "/products",
        },
        content_type="application/json",
    )
    assert created.status_code == 201, created.content
    section_id = created.json()["id"]

    changed = client.patch(
        f"/api/admin/homepage/sections/{section_id}/",
        {"title": "پیشنهادهای ویژه"},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content

    history_response = client.get(f"/api/admin/homepage/sections/{section_id}/revisions/")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 2
    assert history[0]["action"] == HomepageSectionRevision.ACTION_UPDATED
    assert history[0]["snapshot"]["title"] == "پیشنهادهای ویژه"
    original = history[1]
    assert original["action"] == HomepageSectionRevision.ACTION_CREATED
    assert original["snapshot"]["title"] == "جدیدترین‌ها"

    restored = client.post(
        f"/api/admin/homepage/sections/{section_id}/revisions/",
        {"revision_id": original["id"]},
        content_type="application/json",
    )
    assert restored.status_code == 200, restored.content
    assert restored.json()["title"] == "جدیدترین‌ها"
    section = HomepageSection.objects.get(pk=section_id)
    assert section.title == "جدیدترین‌ها"
    assert section.revisions.count() == 3
    assert section.revisions.first().action == HomepageSectionRevision.ACTION_ROLLBACK


def test_homepage_section_revision_permissions_are_separate(make_staff):
    section = HomepageSection.objects.create(
        title="جدیدترین‌ها",
        section_type=HomepageSection.TYPE_NEWEST_PRODUCTS,
    )
    read_only = client_for(make_staff("catalog.view_homepagesection"))
    assert read_only.get(f"/api/admin/homepage/sections/{section.pk}/revisions/").status_code == 200
    assert read_only.post(
        f"/api/admin/homepage/sections/{section.pk}/revisions/",
        {"revision_id": 1},
        content_type="application/json",
    ).status_code == 403

    no_read = client_for(make_staff("catalog.change_homepagesection"))
    assert no_read.get(f"/api/admin/homepage/sections/{section.pk}/revisions/").status_code == 403
