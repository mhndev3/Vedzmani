from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

import pytest

from apps.catalog.models import Category, ColorVariant, HomepageBanner, Product, VariantImage
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def banner_permissions():
    return (
        "catalog.add_homepagebanner",
        "catalog.view_homepagebanner",
        "catalog.change_homepagebanner",
        "catalog.view_variantimage",
    )


def test_banner_can_reuse_product_media_without_copying_file(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    key = "products/1/1/reusable.webp"
    default_storage.save(key, ContentFile(b"existing-webp-content"))

    category = Category.objects.create(name="لباس", slug="clothing")
    product = Product.objects.create(
        category=category, name="بافت آبی", slug="blue-knit", price=100000
    )
    variant = ColorVariant.objects.create(product=product, name="آبی", slug="blue")
    image = VariantImage.objects.create(
        variant=variant,
        storage_key=key,
        display_storage_key=key,
        alt_text="بافت آبی",
        width=640,
        height=800,
    )
    client = client_for(make_staff(*banner_permissions()))

    response = client.post(
        "/api/admin/homepage/banners/",
        {
            "title": "بنر با تصویر محصول",
            "alt_text": "نمای بافت آبی",
            "desktop_image_media_ref": f"product-{image.pk}",
            "status": "draft",
        },
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    banner = HomepageBanner.objects.get(pk=response.json()["id"])
    assert banner.desktop_image.name == key
    assert default_storage.exists(key)


def test_banner_can_reuse_another_banner_image_and_mobile_slot(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    key = "homepage-banners/source.webp"
    default_storage.save(key, ContentFile(b"existing-banner-image"))
    source = HomepageBanner.objects.create(
        title="بنر منبع",
        alt_text="تصویر منبع",
        desktop_image=key,
    )
    client = client_for(make_staff(*banner_permissions()))

    response = client.post(
        "/api/admin/homepage/banners/",
        {
            "title": "بنر مقصد",
            "alt_text": "تصویر مقصد",
            "desktop_image_media_ref": f"banner-{source.pk}-desktop_image",
            "mobile_image_media_ref": f"banner-{source.pk}-desktop_image",
            "status": "draft",
        },
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    banner = HomepageBanner.objects.get(pk=response.json()["id"])
    assert banner.desktop_image.name == key
    assert banner.mobile_image.name == key


def test_banner_media_reference_requires_source_permission_and_existing_image(make_staff, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    key = "products/1/1/private.webp"
    default_storage.save(key, ContentFile(b"existing-webp-content"))
    category = Category.objects.create(name="لباس", slug="clothing")
    product = Product.objects.create(
        category=category, name="بافت", slug="knit", price=100000
    )
    variant = ColorVariant.objects.create(product=product, name="مشکی", slug="black")
    image = VariantImage.objects.create(
        variant=variant, storage_key=key, width=400, height=500
    )

    no_media_permission = client_for(make_staff(
        "catalog.add_homepagebanner", "catalog.view_homepagebanner", "catalog.change_homepagebanner"
    ))
    denied = no_media_permission.post(
        "/api/admin/homepage/banners/",
        {"alt_text": "تصویر", "desktop_image_media_ref": f"product-{image.pk}"},
        content_type="application/json",
    )
    assert denied.status_code == 400

    allowed = client_for(make_staff(*banner_permissions()))
    missing = allowed.post(
        "/api/admin/homepage/banners/",
        {"alt_text": "تصویر", "desktop_image_media_ref": "product-999999"},
        content_type="application/json",
    )
    assert missing.status_code == 400
