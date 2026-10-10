"""Catalog admin: pages render, validation errors are form errors (never 500), and no N+1 in changelists."""

from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Collection, Product, VariantImage, VariantSize
from tests.conftest import new_phone

pytestmark = pytest.mark.django_db


def _formset(prefix, total=0, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def _product_form(category, **over):
    data = {"name": "Hoodie", "slug": "hoodie", "category": category.pk, "description": "", "price": "1000"}
    data.update(_formset("color_variants"))
    data.update(over)
    return data


# --- pages ----------------------------------------------------------------------
def test_change_pages_render_with_inlines(su_client, make_variant_size):
    vs = make_variant_size()
    variant, product = vs.variant, vs.variant.product
    Collection.objects.create(name="Winter", slug="winter")
    for url in (
        f"/admin/catalog/product/{product.pk}/change/",
        f"/admin/catalog/colorvariant/{variant.pk}/change/",
        f"/admin/catalog/variantsize/{vs.pk}/change/",
        f"/admin/catalog/variantimage/{variant.images.get().pk}/change/",
        f"/admin/catalog/category/{product.category.pk}/change/",
        f"/admin/catalog/collection/{Collection.objects.get().pk}/change/",
        f"/admin/catalog/size/{vs.size.pk}/change/",
    ):
        assert su_client.get(url).status_code == 200, url


def test_current_price_is_shown_read_only_not_stored(su_client, make_variant_size):
    product = make_variant_size().variant.product
    product.sale_price = Decimal("800")
    product.save()
    html = su_client.get("/admin/catalog/product/").content.decode()
    assert 'field-current_price">800<' in html
    assert "current_price" not in {f.name for f in Product._meta.get_fields()}
    change = su_client.get(f"/admin/catalog/product/{product.pk}/change/").content.decode()
    assert "field-current_price" in change and 'name="current_price"' not in change


def test_staff_can_search_products_by_sku(su_client, make_variant_size):
    vs = make_variant_size()
    make_variant_size()
    html = su_client.get("/admin/catalog/product/", {"q": vs.sku}).content.decode()
    assert vs.variant.product.name in html and "1 product" in html


# --- validation -------------------------------------------------------------------
def test_product_add_defaults_to_unpublished(su_client):
    category = Category.objects.create(name="C", slug="c")
    assert su_client.post("/admin/catalog/product/add/", _product_form(category)).status_code == 302
    assert Product.objects.get(slug="hoodie").is_active is False


@pytest.mark.parametrize("sale", ["1000", "1500", "0"])
def test_product_add_rejects_invalid_sale_price_without_500(su_client, sale):
    category = Category.objects.create(name="C", slug="c")
    response = su_client.post("/admin/catalog/product/add/", _product_form(category, sale_price=sale))
    assert response.status_code == 200 and not Product.objects.exists()


def test_variant_page_can_add_size_with_stock(su_client, make_variant_size):
    variant = make_variant_size().variant
    size = variant.sizes.get().size
    variant.sizes.all().delete()
    data = {
        "product": variant.product_id, "name": variant.name, "slug": variant.slug, "hex_color": variant.hex_color,
        "position": variant.position, "is_active": "on",
        **_formset("sizes", total=1),
        "sizes-0-size": size.pk, "sizes-0-sku": "NEW-SKU-1", "sizes-0-stock_quantity": "7", "sizes-0-is_active": "on",
        **_formset("images", total=1, initial=1),
        "images-0-id": variant.images.get().pk, "images-0-variant": variant.pk,
        "images-0-storage_key": variant.images.get().storage_key, "images-0-position": "0",
        "images-0-is_primary": "on", "images-0-width": "10", "images-0-height": "10",
        "images-0-content_type": "image/webp", "images-0-is_active": "on",
    }
    assert su_client.post(f"/admin/catalog/colorvariant/{variant.pk}/change/", data).status_code == 302
    assert VariantSize.objects.get(sku="NEW-SKU-1").stock_quantity == 7

def test_two_primary_images_in_one_submission_is_a_form_error(su_client, make_variant_size):
    variant = make_variant_size().variant
    variant.images.all().delete()
    data = {
        "product": variant.product_id, "name": variant.name, "slug": variant.slug, "hex_color": variant.hex_color,
        "position": variant.position, "is_active": "on",
        **_formset("sizes"),
        **_formset("images", total=2),
    }
    for i in (0, 1):
        data.update({
            f"images-{i}-storage_key": f"x/{i}.webp", f"images-{i}-position": str(i), f"images-{i}-is_primary": "on",
            f"images-{i}-width": "10", f"images-{i}-height": "10", f"images-{i}-content_type": "image/webp",
            f"images-{i}-is_active": "on",
        })
    response = su_client.post(f"/admin/catalog/colorvariant/{variant.pk}/change/", data)
    assert response.status_code == 200 and b"Only one image" in response.content
    assert not VariantImage.objects.filter(variant=variant).exists()


@pytest.mark.parametrize("new_sorts_first", [False, True])
def test_moving_primary_image_flag_works_in_one_save_in_either_order(su_client, make_variant_size, new_sorts_first):
    variant = make_variant_size().variant
    old = variant.images.get()
    old.position = 5 if new_sorts_first else 0
    old.save()
    new = VariantImage.objects.create(
        variant=variant, storage_key="swap/new.webp", position=1, width=10, height=10
    )
    data = {
        "product": variant.product_id, "name": variant.name, "slug": variant.slug, "hex_color": variant.hex_color,
        "position": variant.position, "is_active": "on", **_formset("sizes"), **_formset("images", total=2, initial=2),
    }
    for i, image in enumerate(sorted([old, new], key=lambda im: im.position)):
        data.update({
            f"images-{i}-id": image.pk, f"images-{i}-variant": variant.pk, f"images-{i}-storage_key": image.storage_key,
            f"images-{i}-position": str(image.position), f"images-{i}-width": "10", f"images-{i}-height": "10",
            f"images-{i}-content_type": "image/webp", f"images-{i}-is_active": "on",
        })
        if image.pk == new.pk:
            data[f"images-{i}-is_primary"] = "on"
    assert su_client.post(f"/admin/catalog/colorvariant/{variant.pk}/change/", data).status_code == 302
    assert list(variant.images.filter(is_primary=True)) == [new]

# --- N+1 guard ------------------------------------------------------------------------
LIST_URLS = [
    "/admin/accounts/user/", "/admin/catalog/category/", "/admin/catalog/collection/", "/admin/catalog/size/",
    "/admin/catalog/product/", "/admin/catalog/colorvariant/", "/admin/catalog/variantsize/",
    "/admin/catalog/variantimage/", "/admin/cart/cart/", "/admin/cart/cartitem/",
]


def _populate(n, make_variant_size):
    for _ in range(n):
        vs = make_variant_size()
        collection = Collection.objects.create(name=f"Col {vs.pk}", slug=f"col-{vs.pk}")
        vs.variant.product.collections.add(collection)
        cart = Cart.objects.create(user=User.objects.create_user(new_phone()))
        CartItem.objects.create(cart=cart, variant_size=vs, quantity=2)


def _query_counts(client):
    counts = {}
    for url in LIST_URLS:
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(url).status_code == 200, url
        counts[url] = len(ctx)
    return counts


def test_changelists_do_not_issue_per_row_queries(su_client, make_variant_size):
    _populate(2, make_variant_size)
    small = _query_counts(su_client)
    _populate(8, make_variant_size)
    large = _query_counts(su_client)
    assert large == small
