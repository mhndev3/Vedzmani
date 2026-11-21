import json

import pytest

from tests.conftest import client_for


pytestmark = pytest.mark.django_db


def valid_settings(**overrides):
    value = {
        "primary": "#223344",
        "primary_foreground": "#ffffff",
        "accent": "#eeeeee",
        "accent_foreground": "#111111",
        "font": "persian-modern",
        "radius": "rounded",
        "motion": "subtle",
    }
    value.update(overrides)
    return {"settings": value}


def test_storefront_theme_admin_requires_staff_and_model_permissions(customer_client, make_staff):
    assert customer_client.get("/api/admin/storefront/theme/").status_code in (401, 403)
    assert client_for(make_staff()).get("/api/admin/storefront/theme/").status_code == 403


def test_theme_draft_is_not_public_until_published(make_staff):
    client = client_for(make_staff(
        "catalog.view_storefronttheme",
        "catalog.change_storefronttheme",
    ))
    draft = valid_settings()
    response = client.patch(
        "/api/admin/storefront/theme/",
        data=json.dumps(draft),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["draft_settings"] == draft["settings"]

    public_before = client.get("/api/catalog/storefront/theme/")
    assert public_before.status_code == 200
    assert public_before.json()["settings"]["primary"] == "#171717"

    published = client.post(
        "/api/admin/storefront/theme/",
        data='{"action":"publish"}',
        content_type="application/json",
    )
    assert published.status_code == 200, published.content
    public_after = client.get("/api/catalog/storefront/theme/")
    assert public_after.json()["settings"] == draft["settings"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"primary": "red"},
        {"font": "external-font-url"},
        {"radius": "999px"},
        {"motion": "javascript:alert(1)"},
    ],
)
def test_theme_rejects_unapproved_tokens(make_staff, overrides):
    client = client_for(make_staff(
        "catalog.view_storefronttheme",
        "catalog.change_storefronttheme",
    ))
    response = client.patch(
        "/api/admin/storefront/theme/",
        data=json.dumps(valid_settings(**overrides)),
        content_type="application/json",
    )
    assert response.status_code == 400
