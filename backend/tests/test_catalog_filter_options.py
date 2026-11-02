import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Category, Collection, ColorVariant, Size
from tests.test_catalog_listing import make

pytestmark = pytest.mark.django_db

URL = "/api/catalog/filters/"


def test_knitwear_category_is_seeded():
    category = Category.objects.get(slug="knitwear")
    assert category.name == "بافت"
    assert category.is_active is True
    assert category.position == 11


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
    assert sorted(s["code"] for s in data["sizes"]) == ["m", "s"]


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



def test_dependent_filter_options_are_scoped_to_selected_categories():
    make("hoodie", category="hoodie", collections=["winter"], variants={"black": {"m": 1}})
    make("trousers", category="trousers", collections=["summer"], variants={"red": {"xl": 1}})

    data = Client().get(URL, {"category": "hoodie"}).json()

    # Customers can still change the top-level category, but dependent filters
    # only show values that exist in the selected category.
    assert sorted(c["slug"] for c in data["categories"]) == ["hoodie", "trousers"]
    assert [c["slug"] for c in data["collections"]] == ["winter"]
    assert [c["slug"] for c in data["colors"]] == ["black"]
    assert [s["code"] for s in data["sizes"]] == ["m"]


def test_dependent_filter_options_accept_multiple_selected_categories():
    make("hoodie", category="hoodie", collections=["winter"], variants={"black": {"m": 1}})
    make("trousers", category="trousers", collections=["summer"], variants={"red": {"xl": 1}})

    data = Client().get(f"{URL}?category=hoodie&category=trousers").json()

    assert sorted(c["slug"] for c in data["collections"]) == ["summer", "winter"]
    assert sorted(c["slug"] for c in data["colors"]) == ["black", "red"]
    assert sorted(s["code"] for s in data["sizes"]) == ["m", "xl"]


def test_filter_options_exclude_sizes_with_zero_stock():
    make("live", category="hoodie", variants={"black": {"m": 2, "xxxl": 0}})

    data = Client().get(URL, {"category": "hoodie"}).json()

    assert [s["code"] for s in data["sizes"]] == ["m"]
