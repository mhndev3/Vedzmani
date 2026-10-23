"""Admin operations: stock availability filter and the static assets the admin pages request.

Static files: these tests cover the Django side only (the URLs the pages ask for and what `collectstatic` produces).
Whether those URLs are actually served in the deployed topology (Nginx / WhiteNoise / CDN) cannot be tested here; see
the "Static files" section of backend/ADMIN.md.
"""

import re

import pytest
from django.core.management import call_command
from django.test import Client

from tests.conftest import client_for

pytestmark = pytest.mark.django_db

LIST = "/admin/catalog/variantsize/"


def listed_ids(response):
    assert response.status_code == 200
    return {row.pk for row in response.context["cl"].result_list}


# --- stock availability filter ------------------------------------------------------------------------------
def test_stock_filter_separates_sold_out_from_available(su_client, make_variant_size):
    sold_out, few, many = make_variant_size(stock=0), make_variant_size(stock=3), make_variant_size(stock=7)

    assert listed_ids(su_client.get(LIST)) == {sold_out.pk, few.pk, many.pk}
    assert listed_ids(su_client.get(LIST, {"stock": "out"})) == {sold_out.pk}
    assert listed_ids(su_client.get(LIST, {"stock": "in"})) == {few.pk, many.pk}


def test_stock_filter_ignores_unknown_values(su_client, make_variant_size):
    first, second = make_variant_size(stock=0), make_variant_size(stock=2)
    assert listed_ids(su_client.get(LIST, {"stock": "nonsense"})) == {first.pk, second.pk}


def test_stock_filter_is_offered_in_the_sidebar(su_client, make_variant_size):
    make_variant_size(stock=1)
    html = su_client.get(LIST).content.decode()
    assert "Out of stock" in html and "In stock" in html


def test_view_only_staff_can_use_the_stock_filter_but_not_change_stock(make_staff, make_variant_size):
    sold_out = make_variant_size(stock=0)
    client = client_for(make_staff("catalog.view_variantsize"))
    assert listed_ids(client.get(LIST, {"stock": "out"})) == {sold_out.pk}
    assert client.post(f"{LIST}{sold_out.pk}/change/", {"stock_quantity": "99"}).status_code == 403
    sold_out.refresh_from_db()
    assert sold_out.stock_quantity == 0


# --- static files ------------------------------------------------------------------------------------------
ASSET_REF = re.compile(r'(?:href|src)="(/static/[^"?#]+)')


def test_static_url_is_the_root_relative_path_the_deployment_docs_rely_on(settings):
    assert settings.STATIC_URL == "/static/"


def test_collectstatic_produces_every_asset_the_admin_pages_request(su_client, settings, tmp_path):
    settings.STATIC_ROOT = tmp_path / "staticfiles"  # never the real STATIC_ROOT
    call_command("collectstatic", interactive=False, verbosity=0)

    requested = set(ASSET_REF.findall(Client().get("/admin/login/").content.decode()))
    for page in (
        "/admin/",
        "/admin/catalog/product/",
        "/admin/catalog/variantsize/",
        "/admin/orders/order/",
        "/admin/inventory/inventoryadjustment/add/",  # autocomplete widget: select2 assets
    ):
        response = su_client.get(page)
        assert response.status_code == 200, page
        requested |= set(ASSET_REF.findall(response.content.decode()))

    assert "/static/admin/css/base.css" in requested
    assert any(url.endswith(".js") for url in requested)
    missing = sorted(url for url in requested if not (settings.STATIC_ROOT / url.removeprefix("/static/")).is_file())
    assert not missing, f"collectstatic did not produce: {missing}"
