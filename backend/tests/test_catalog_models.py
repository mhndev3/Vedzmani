from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

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


@pytest.fixture
def category():
    return Category.objects.create(name="Hoodie", slug="hoodie")


@pytest.fixture
def product(category):
    return Product.objects.create(category=category, name="Basic Hoodie", slug="basic-hoodie", price=Decimal("1000000"))


@pytest.fixture
def variant(product):
    return ColorVariant.objects.create(product=product, name="Black", slug="black", hex_color="#000000")


def make_image(variant, key, position, **kw):
    return VariantImage.objects.create(
        variant=variant, storage_key=key, position=position, width=800, height=1000, **kw
    )


def test_category_and_slug_unique(category):
    with pytest.raises(IntegrityError), transaction.atomic():
        Category.objects.create(name="Other", slug="hoodie")


def test_product_defaults_unpublished_and_relations(product, category):
    assert product.is_active is False
    assert product.category == category
    assert product.current_price == Decimal("1000000")


def test_product_slug_unique(product, category):
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(category=category, name="X", slug="basic-hoodie", price=Decimal("5"))


def test_product_price_must_be_positive_in_db(category):
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(category=category, name="X", slug="x", price=Decimal("0"))


@pytest.mark.parametrize("sale", [Decimal("1000000"), Decimal("2000000"), Decimal("0")])
def test_sale_price_must_be_below_price_in_db(category, sale):
    with pytest.raises(IntegrityError), transaction.atomic():
        Product.objects.create(category=category, name="X", slug="x", price=Decimal("1000000"), sale_price=sale)


def test_current_price_uses_sale_price(category):
    p = Product.objects.create(category=category, name="X", slug="x", price=Decimal("100"), sale_price=Decimal("80"))
    assert p.current_price == Decimal("80")


def test_category_with_products_is_protected(product, category):
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        category.delete()


def test_product_collections_m2m(product):
    c = Collection.objects.create(name="Winter", slug="winter")
    product.collections.add(c)
    assert list(c.products.all()) == [product]


def test_multiple_color_variants_and_duplicate_slug_rejected(product, variant):
    ColorVariant.objects.create(product=product, name="White", slug="white", hex_color="#FFFFFF")
    assert product.color_variants.count() == 2
    with pytest.raises(IntegrityError), transaction.atomic():
        ColorVariant.objects.create(product=product, name="Black 2", slug="black")


def test_same_color_slug_allowed_on_other_product(product, variant, category):
    other = Product.objects.create(category=category, name="Y", slug="y", price=Decimal("10"))
    ColorVariant.objects.create(product=other, name="Black", slug="black")


@pytest.mark.parametrize("bad", ["000000", "#00000", "#GGGGGG", "red"])
def test_hex_color_validation(product, bad):
    v = ColorVariant(product=product, name="C", slug="c", hex_color=bad)
    with pytest.raises(ValidationError):
        v.full_clean()


def test_variant_sizes_and_duplicate_combination_rejected(variant):
    s, m = Size.objects.create(code="s", label="S", position=1), Size.objects.create(code="m", label="M", position=2)
    VariantSize.objects.create(variant=variant, size=m, sku="BH-BLK-M", stock_quantity=3)
    VariantSize.objects.create(variant=variant, size=s, sku="BH-BLK-S")
    assert [vs.size.code for vs in variant.sizes.all()] == ["s", "m"]  # ordered by size position
    with pytest.raises(IntegrityError), transaction.atomic():
        VariantSize.objects.create(variant=variant, size=s, sku="BH-BLK-S-2")


def test_sku_unique_and_stock_not_negative(variant):
    s = Size.objects.create(code="s", label="S")
    m = Size.objects.create(code="m", label="M")
    VariantSize.objects.create(variant=variant, size=s, sku="SKU1")
    with pytest.raises(IntegrityError), transaction.atomic():
        VariantSize.objects.create(variant=variant, size=m, sku="SKU1")
    with pytest.raises(IntegrityError), transaction.atomic():
        VariantSize.objects.create(variant=variant, size=m, sku="SKU2", stock_quantity=-1)


def test_size_in_use_is_protected(variant):
    from django.db.models import ProtectedError

    s = Size.objects.create(code="s", label="S")
    VariantSize.objects.create(variant=variant, size=s, sku="SKU1")
    with pytest.raises(ProtectedError):
        s.delete()


def test_variant_images_ordering_and_primary(variant):
    make_image(variant, "p/1/black/b.webp", 2)
    make_image(variant, "p/1/black/a.webp", 1, is_primary=True)
    assert [i.storage_key for i in variant.images.all()] == ["p/1/black/a.webp", "p/1/black/b.webp"]
    assert variant.images.get(is_primary=True).storage_key == "p/1/black/a.webp"


def test_image_position_unique_per_variant(variant, product):
    make_image(variant, "a.webp", 1)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_image(variant, "b.webp", 1)
    other = ColorVariant.objects.create(product=product, name="White", slug="white")
    make_image(other, "c.webp", 1)  # same position on another variant is fine


def test_only_one_primary_image_per_variant(variant, product):
    make_image(variant, "a.webp", 1, is_primary=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_image(variant, "b.webp", 2, is_primary=True)
    other = ColorVariant.objects.create(product=product, name="White", slug="white")
    make_image(other, "c.webp", 1, is_primary=True)


def test_storage_key_unique(variant):
    make_image(variant, "a.webp", 1)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_image(variant, "a.webp", 2)


def test_non_webp_content_type_rejected_by_db_and_validation(variant):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_image(variant, "a.webp", 1, content_type="image/png")
    img = VariantImage(variant=variant, storage_key="a.webp", position=1, width=1, height=1, content_type="image/png")
    with pytest.raises(ValidationError):
        img.full_clean()


@pytest.mark.parametrize("key", ["a.png", "/abs/a.webp", "x/../a.webp", "x//a.webp", ""])
def test_storage_key_validation(variant, key):
    img = VariantImage(variant=variant, storage_key=key, position=1, width=1, height=1)
    with pytest.raises(ValidationError):
        img.full_clean()


def test_image_dimensions_positive_in_db(variant):
    with pytest.raises(IntegrityError), transaction.atomic():
        VariantImage.objects.create(variant=variant, storage_key="a.webp", position=1, width=0, height=10)


def test_image_url_uses_cdn_base(variant, settings):
    settings.MEDIA_CDN_BASE_URL = "https://cdn.example.com/"
    assert make_image(variant, "p/a.webp", 1).url == "https://cdn.example.com/p/a.webp"


def test_deleting_product_cascades_to_variant_tree(product, variant):
    s = Size.objects.create(code="s", label="S")
    VariantSize.objects.create(variant=variant, size=s, sku="SKU1")
    make_image(variant, "a.webp", 1)
    product.delete()
    assert not ColorVariant.objects.exists() and not VariantSize.objects.exists() and not VariantImage.objects.exists()
