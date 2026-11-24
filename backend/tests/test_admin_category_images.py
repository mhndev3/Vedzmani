from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test.client import BOUNDARY, encode_multipart
from PIL import Image
from rest_framework.test import APIClient

from apps.catalog.models import Category, HomepageSection, Product
from tests.conftest import client_for


pytestmark = pytest.mark.django_db


def uploaded_image(name="category.png", color=(20, 80, 160)):
    buffer = BytesIO()
    Image.new("RGB", (48, 48), color).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

def multipart_patch(client, path, data):
    return client.generic(
        "PATCH",
        path,
        encode_multipart(BOUNDARY, data),
        content_type=f"multipart/form-data; boundary={BOUNDARY}",
    )


@override_settings(MEDIA_ROOT="/tmp/vedzmani-test-category-images")
def test_staff_can_upload_replace_and_remove_category_image(make_staff):
    editor = client_for(make_staff("catalog.add_category", "catalog.view_category", "catalog.change_category"))

    created = editor.post(
        "/api/admin/catalog/categories/",
        {"name": "بافت", "slug": "category-image-knitwear", "position": 0, "image": uploaded_image()},
        format="multipart",
    )
    assert created.status_code == 201, created.content
    category = Category.objects.get(pk=created.data["id"])
    first_name = category.image.name
    assert first_name.startswith("categories/")
    assert created.data["image_url"].endswith(first_name)
    assert category.image.storage.exists(first_name)

    replaced = multipart_patch(
        editor,
        f"/api/admin/catalog/categories/{category.pk}/",
        {"image": uploaded_image(color=(180, 40, 60))},
    )
    assert replaced.status_code == 200, replaced.content
    category.refresh_from_db()
    second_name = category.image.name
    assert second_name != first_name
    assert category.image.storage.exists(second_name)
    assert not category.image.storage.exists(first_name)

    removed = multipart_patch(
        editor,
        f"/api/admin/catalog/categories/{category.pk}/",
        {"remove_image": "true"},
    )
    assert removed.status_code == 200, removed.content
    category.refresh_from_db()
    assert not category.image
    assert not category.image.storage.exists(second_name)


def test_category_image_upload_requires_category_change_permission(make_staff):
    category = Category.objects.create(name="لباس", slug="category-image-permission")
    viewer = client_for(make_staff("catalog.view_category"))
    response = multipart_patch(
        viewer,
        f"/api/admin/catalog/categories/{category.pk}/",
        {"image": uploaded_image()},
    )
    assert response.status_code == 403
    category.refresh_from_db()
    assert not category.image


@override_settings(MEDIA_ROOT="/tmp/vedzmani-test-category-images")
def test_public_homepage_and_filter_api_return_category_image():
    category = Category.objects.create(
        name="دورس",
        slug="category-image-public",
        image=uploaded_image(),
    )
    Product.objects.create(
        category=category,
        name="دورس آزمایشی",
        slug="category-image-public-product",
        price="1000000",
        is_active=True,
    )
    section = HomepageSection.objects.create(
        title="دسته‌بندی‌ها",
        section_type=HomepageSection.TYPE_CATEGORIES,
        status=HomepageSection.STATUS_PUBLISHED,
    )
    section.categories.add(category)

    filters = APIClient().get("/api/catalog/filters/")
    assert filters.status_code == 200
    filter_category = next(item for item in filters.data["categories"] if item["slug"] == category.slug)
    assert filter_category["image"]["url"].endswith(category.image.name)

    homepage = APIClient().get("/api/catalog/homepage-sections/")
    assert homepage.status_code == 200
    public_category = homepage.data["sections"][0]["categories"][0]
    assert public_category["image"]["url"].endswith(category.image.name)
    assert public_category["image"]["alt_text"] == category.name


def test_invalid_category_image_is_rejected(make_staff):
    editor = client_for(make_staff("catalog.add_category", "catalog.view_category"))
    invalid = SimpleUploadedFile("not-an-image.png", b"not an image", content_type="image/png")
    response = editor.post(
        "/api/admin/catalog/categories/",
        {"name": "نامعتبر", "slug": "category-invalid-image", "image": invalid},
        format="multipart",
    )
    assert response.status_code == 400
