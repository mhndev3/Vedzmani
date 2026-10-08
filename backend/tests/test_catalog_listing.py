from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from apps.catalog.models import (
    Category,
    Collection,
    ColorVariant,
    Product,
    Size,
    VariantImage,
    VariantSize,
)

pytestmark = pytest.mark.django_db

URL = "/api/catalog/products/"


def get(**params):
    return Client().get(URL, params)


def slugs(response):
    return [p["slug"] for p in response.json()["results"]]


_sizes: dict = {}


def size(code):
    if code not in _sizes or not Size.objects.filter(pk=_sizes[code].pk).exists():
        _sizes[code] = Size.objects.get_or_create(code=code, defaults={"label": code.upper(), "position": len(_sizes)})[0]
    return _sizes[code]


def make(
    slug,
    *,
    name=None,
    category="hoodie",
    price=1000,
    sale=None,
    active=True,
    description="",
    collections=(),
    variants=None,
    age_days=0,
):
    """variants: {"black": {"m": 5, "l": 0}, "white": {"s": 2}}  (color slug -> {size code: stock})."""
    cat = Category.objects.get_or_create(slug=category, defaults={"name": category.title()})[0]
    p = Product.objects.create(
        category=cat,
        name=name or slug.replace("-", " ").title(),
        slug=slug,
        description=description,
        price=Decimal(price),
        sale_price=Decimal(sale) if sale else None,
        is_active=active,
    )
    Product.objects.filter(pk=p.pk).update(created_at=timezone.now() - timedelta(days=age_days))
    for c in collections:
        p.collections.add(Collection.objects.get_or_create(slug=c, defaults={"name": c.title()})[0])
    for pos, (color, sizes) in enumerate((variants if variants is not None else {"black": {"m": 1}}).items()):
        v = ColorVariant.objects.create(product=p, name=color.title(), slug=color, hex_color="#000000", position=pos)
        for code, stock in sizes.items():
            VariantSize.objects.create(variant=v, size=size(code), sku=f"{slug}-{color}-{code}", stock_quantity=stock)
    return p


def add_image(variant, key, *, position=0, primary=False, active=True):
    return VariantImage.objects.create(
        variant=variant, storage_key=key, position=position, is_primary=primary, width=800, height=1000,
        alt_text="alt", is_active=active,
    )


# 1. basic listing ---------------------------------------------------------------------------------


def test_basic_listing_shape_and_no_private_fields():
    p = make("alpha", variants={"black": {"m": 3}, "white": {"s": 0}})
    add_image(p.color_variants.get(slug="black"), "alpha/b0.webp", primary=True)
    r = get()
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"count", "next", "previous", "results"} and body["count"] == 1
    item = body["results"][0]
    assert set(item) == {"id", "name", "slug", "price", "sale_price", "category", "in_stock", "image", "colors"}
    assert item["category"] == {"name": "Hoodie", "slug": "hoodie"}
    assert item["in_stock"] is True
    assert item["image"] == {"url": "/alpha/b0.webp", "alt_text": "alt", "width": 800, "height": 1000}
    assert [c["slug"] for c in item["colors"]] == ["black", "white"]
    raw = r.content.decode()
    for secret in ("stock_quantity", "sku", "storage_key", "is_active", "description"):
        assert secret not in raw


def test_listing_is_public_and_read_only():
    make("alpha")
    assert Client().get(URL).status_code == 200  # no auth, no CSRF needed
    assert Client().post(URL).status_code == 405


def test_representative_image_prefers_first_variant_primary_and_skips_inactive():
    p = make("alpha", variants={"black": {"m": 1}, "white": {"m": 1}})
    black, white = p.color_variants.get(slug="black"), p.color_variants.get(slug="white")
    add_image(black, "a/black-1.webp", position=1)
    add_image(black, "a/black-0.webp", position=0, primary=True, active=False)  # inactive primary ignored
    add_image(white, "a/white-0.webp", position=0, primary=True)
    assert get().json()["results"][0]["image"]["url"] == "/a/black-1.webp"
    make("no-image")
    assert next(i for i in get().json()["results"] if i["slug"] == "no-image")["image"] is None


# 2. pagination / 17. accurate count ---------------------------------------------------------------


def test_pagination_count_next_previous():
    for n in range(5):
        make(f"p{n}", age_days=n)  # p0 newest
    first = get(page_size=2).json()
    assert first["count"] == 5 and len(first["results"]) == 2
    assert first["previous"] is None and "page=2" in first["next"]
    assert [p["slug"] for p in first["results"]] == ["p0", "p1"]
    last = get(page_size=2, page=3).json()
    assert [p["slug"] for p in last["results"]] == ["p4"] and last["next"] is None and "page=2" in last["previous"]
    assert get(page=99).status_code == 404


def test_page_size_is_capped():
    cat = Category.objects.create(name="Bulk", slug="bulk")
    Product.objects.bulk_create(
        [Product(category=cat, name=f"B{n}", slug=f"b{n}", price=Decimal("10"), is_active=True) for n in range(65)]
    )
    body = get(page_size=1000).json()
    assert body["count"] == 65 and len(body["results"]) == 60
    assert len(get().json()["results"]) == 24  # default


def test_count_matches_filtered_total_not_page():
    for n in range(7):
        make(f"in{n}", category="hoodie")
    make("other", category="pants")
    body = get(category="hoodie", page_size=3).json()
    assert body["count"] == 7 and len(body["results"]) == 3


# 3. search ----------------------------------------------------------------------------------------


def test_search_fields_and_case_insensitivity():
    make("red-jacket", name="Crimson Jacket", description="Warm wool lining", category="outerwear", collections=["winter"])
    make("plain-tee", name="Plain Tee", category="tops")
    assert slugs(get(search="crimson")) == ["red-jacket"]  # name
    assert slugs(get(search="WOOL")) == ["red-jacket"]  # description
    assert slugs(get(search="outerwear")) == ["red-jacket"]  # category name
    assert slugs(get(search="winter")) == ["red-jacket"]  # collection name
    assert slugs(get(search="red-jacket")) == ["red-jacket"]  # slug
    assert get(search="nothing-like-this").json()["count"] == 0


def test_search_terms_are_anded_and_wildcards_are_literal():
    make("a", name="Black Hoodie")
    make("b", name="Black Pants", category="pants")
    assert slugs(get(search="black hoodie")) == ["a"]
    assert get(search="%").json()["count"] == 0  # '%' is not a LIKE wildcard
    assert get(search="").json()["count"] == 2  # blank search = no filter


def test_search_ignores_inactive_collection_names():
    make("a", collections=["secret"])
    Collection.objects.filter(slug="secret").update(is_active=False)
    assert get(search="secret").json()["count"] == 0


# 4-5. category / collection -----------------------------------------------------------------------


def test_category_filter_single_multiple_and_unknown():
    make("h", category="hoodie")
    make("p", category="pants")
    make("t", category="tops")
    assert slugs(get(category="pants")) == ["p"]
    assert sorted(slugs(get(category="pants,tops"))) == ["p", "t"]
    assert get(category="unknown").json()["count"] == 0


def test_collection_filter_and_inactive_collection():
    make("a", collections=["summer"])
    make("b", collections=["winter"])
    make("c")
    assert slugs(get(collection="summer")) == ["a"]
    Collection.objects.filter(slug="summer").update(is_active=False)
    assert get(collection="summer").json()["count"] == 0


# 6-7. color / size --------------------------------------------------------------------------------


def test_color_filter():
    make("a", variants={"black": {"m": 1}})
    make("b", variants={"white": {"m": 1}})
    assert slugs(get(color="black")) == ["a"]
    assert sorted(slugs(get(color="black,white"))) == ["a", "b"]


def test_size_filter():
    make("a", variants={"black": {"s": 1}})
    make("b", variants={"black": {"xl": 1}})
    assert slugs(get(size="xl")) == ["b"]


def test_color_and_size_must_match_the_same_variant():
    make("a", variants={"black": {"s": 1}, "white": {"m": 1}})  # black exists, M exists, but not black+M
    make("b", variants={"black": {"m": 1}})
    assert slugs(get(color="black", size="m")) == ["b"]


def test_inactive_variant_or_size_does_not_match():
    p = make("a", variants={"black": {"m": 1}})
    ColorVariant.objects.filter(product=p).update(is_active=False)
    assert get(color="black").json()["count"] == 0
    ColorVariant.objects.filter(product=p).update(is_active=True)
    VariantSize.objects.filter(variant__product=p).update(is_active=False)
    assert get(size="m").json()["count"] == 0


# 8-9. price ---------------------------------------------------------------------------------------


def test_price_filters_use_sale_price_when_present():
    make("cheap", price=100)
    make("mid", price=500)
    make("discounted", price=900, sale=300)  # effective price 300
    assert slugs(get(min_price=300, sort="price_asc")) == ["discounted", "mid"]
    assert slugs(get(max_price=300, sort="price_asc")) == ["cheap", "discounted"]
    assert slugs(get(min_price=200, max_price=400)) == ["discounted"]
    assert slugs(get(min_price=300, max_price=300)) == ["discounted"]  # inclusive bounds


def test_invalid_price_params_rejected():
    for params in ({"min_price": "abc"}, {"max_price": -1}, {"min_price": 10, "max_price": 5}):
        r = get(**params)
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "validation_error"


# 10. in stock -------------------------------------------------------------------------------------


def test_in_stock_filter_and_flag():
    make("have", variants={"black": {"m": 0, "l": 2}})
    make("none", variants={"black": {"m": 0}})
    p = make("hidden-stock", variants={"black": {"m": 9}})
    VariantSize.objects.filter(variant__product=p).update(is_active=False)  # not purchasable
    assert slugs(get(in_stock="true")) == ["have"]
    items = {i["slug"]: i["in_stock"] for i in get().json()["results"]}
    assert items == {"have": True, "none": False, "hidden-stock": False}
    assert get(in_stock="false").json()["count"] == 3  # only "true" filters


def test_in_stock_with_size_means_that_size_is_in_stock():
    make("a", variants={"black": {"m": 0, "l": 5}})
    make("b", variants={"black": {"m": 5}})
    assert slugs(get(size="m", in_stock="true")) == ["b"]


# 11. combined -------------------------------------------------------------------------------------


def test_combined_filters_search_and_sort():
    make("a", name="Black Hoodie", category="hoodie", collections=["winter"], price=800, variants={"black": {"m": 2}})
    make("b", name="Black Hoodie Pro", category="hoodie", collections=["winter"], price=1200, variants={"black": {"m": 2}})
    make("c", name="Black Hoodie Lite", category="hoodie", collections=["winter"], price=900, variants={"black": {"m": 0}})
    make("d", name="Black Pants", category="pants", collections=["winter"], price=900, variants={"black": {"m": 2}})
    r = get(
        search="hoodie", category="hoodie", collection="winter", color="black", size="m",
        in_stock="true", min_price=700, max_price=1500, sort="price_desc",
    )
    assert slugs(r) == ["b", "a"] and r.json()["count"] == 2


# 12-13. sorting -----------------------------------------------------------------------------------


def test_sort_options():
    make("b-mid", name="Bravo", price=500, age_days=1)
    make("c-new", name="Charlie", price=900, sale=100, age_days=0)  # effective 100
    make("a-old", name="Alpha", price=300, age_days=2)
    assert slugs(get()) == ["c-new", "b-mid", "a-old"]  # default newest
    assert slugs(get(sort="newest")) == ["c-new", "b-mid", "a-old"]
    assert slugs(get(sort="price_asc")) == ["c-new", "a-old", "b-mid"]
    assert slugs(get(sort="price_desc")) == ["b-mid", "a-old", "c-new"]
    assert slugs(get(sort="name_asc")) == ["a-old", "b-mid", "c-new"]
    assert slugs(get(sort="name_desc")) == ["c-new", "b-mid", "a-old"]


def test_sort_ties_are_deterministic_across_pages():
    for n in range(6):
        make(f"t{n}", price=100)
    pages = [slugs(get(sort="price_asc", page_size=2, page=n)) for n in (1, 2, 3)]
    flat = [s for page in pages for s in page]
    assert sorted(flat) == sorted(set(flat)) and len(flat) == 6  # no repeats, no gaps


@pytest.mark.parametrize("bad", ["price", "-price", "id", "name_asc;drop", "created_at"])
def test_invalid_sort_rejected(bad):
    r = get(sort=bad)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error" and "sort" in r.json()["error"]["details"]


def test_blank_sort_uses_default_order():
    make("old", age_days=1)
    make("new", age_days=0)
    assert slugs(get(sort="")) == ["new", "old"]


# 14. duplicates -----------------------------------------------------------------------------------


def test_product_appears_once_despite_many_matching_joins():
    make(
        "multi",
        name="Hoodie Hoodie",
        description="hoodie hoodie",
        collections=["hoodies", "hoodie-club", "more-hoodies"],
        variants={"black": {"s": 1, "m": 1, "l": 1}, "white": {"s": 1, "m": 1, "l": 1}},
    )
    r = get(search="hoodie", collection="hoodies,hoodie-club", color="black,white", size="s,m,l", in_stock="true")
    assert r.json()["count"] == 1 and slugs(r) == ["multi"]


# 15. visibility -----------------------------------------------------------------------------------


def test_unpublished_products_and_inactive_categories_excluded():
    make("live")
    make("draft", active=False)
    make("in-dead-category", category="dead")
    Category.objects.filter(slug="dead").update(is_active=False)
    assert slugs(get()) == ["live"]
    assert get().json()["count"] == 1
    assert get(search="draft").json()["count"] == 0
    assert get(category="dead").json()["count"] == 0


# 16. empty ----------------------------------------------------------------------------------------


def test_empty_catalog_and_empty_filter_result():
    assert get().json() == {"count": 0, "next": None, "previous": None, "results": []}
    make("a")
    assert get(color="nope").json()["results"] == []


def test_malformed_filter_values_rejected():
    assert get(category="a b").status_code == 400
    assert get(color=",".join(f"c{n}" for n in range(11))).status_code == 400


# N+1 regression -----------------------------------------------------------------------------------


def test_listing_query_count_is_constant(django_assert_max_num_queries):
    for n in range(12):
        p = make(f"p{n}", collections=["c1", "c2"], variants={"black": {"s": 1, "m": 1}, "white": {"s": 1}, "red": {"l": 1}})
        for v in p.color_variants.all():
            add_image(v, f"p{n}/{v.slug}-0.webp", position=0, primary=True)
            add_image(v, f"p{n}/{v.slug}-1.webp", position=1)
    with django_assert_max_num_queries(3):  # count + products + color swatches
        r = get(search="p", category="hoodie", in_stock="true", sort="price_asc", page_size=12)
    assert r.status_code == 200 and len(r.json()["results"]) == 12
