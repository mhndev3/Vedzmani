import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Category, Collection, ColorVariant, Size
from tests.test_catalog_listing import make

pytestmark = pytest.mark.django_db

URL = "/api/catalog/filters/"


def test_filter_options_only_include_published_data():
    make("live", category="hoodie", collections=["winter"], variants={"black": {"m": 1, "l": 0}, "white": {"s": 1}})
    make("hidden", category="secret", active=False, collections=["hidden-col"], variants={"red": {"xl": 1}})
    Category.objects.get_or_create(slug="empty", defaults={"name": "Empty"})
    Collection.objects.get_or_create(slug="unused", defaults={"name": "Unused"})
    Size.objects.get_or_create(code="xxl", defaults={"label": "XXL", "position": 99})

    data = Client().get(URL).json()

    assert [c["slug"] for c in data["categories"]] == ["hoodie"]
    assert [c["slug"] for c in data["collections"]] == ["winter"]
    assert sorted(c["slug"] for c in data["colors"]) == ["black", "white"]
    assert sorted(s["code"] for s in data["sizes"]) == ["l", "m", "s"]


def test_filter_options_ignore_inactive_variants():
    make("live", variants={"black": {"m": 1}})
    ColorVariant.objects.filter(slug="black").update(is_active=False)
    assert Client().get(URL).json()["colors"] == []


def test_filter_options_constant_query_count():
    make("a", variants={"black": {"m": 1}})
    with CaptureQueriesContext(connection) as small:
        Client().get(URL)
    for i in range(5):
        make(f"p{i}", category=f"cat{i}", variants={"blue": {"s": 1}, "green": {"l": 1}})
    with CaptureQueriesContext(connection) as big:
        Client().get(URL)
    assert len(big) == len(small)
