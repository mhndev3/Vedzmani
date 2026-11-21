from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from apps.catalog.models import VariantImage
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def png_upload(name="product.png"):
    buffer = BytesIO()
    Image.new("RGB", (32, 48), "skyblue").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def test_staff_can_upload_webp_and_first_image_becomes_primary(make_staff, make_variant_size, tmp_path):
    row = make_variant_size()
    actor = make_staff(
        "catalog.add_variantimage", "catalog.view_variantimage", "catalog.view_colorvariant",
    )
    client = client_for(actor)
    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            "/api/admin/catalog/images/upload/",
            {"variant": row.variant_id, "file": png_upload(), "alt_text": "نمای جلو"},
        )
        assert response.status_code == 201, response.content
        image = VariantImage.objects.get(pk=response.json()["id"])
        assert image.is_primary is True
        assert image.position == 0
        assert image.content_type == "image/webp"
        assert image.storage_key.endswith(".webp")
        assert (tmp_path / image.storage_key).is_file()
        assert "storage_key" not in response.json()
        assert response.json()["url"].endswith(image.storage_key)


def test_image_upload_requires_add_and_color_view_permissions(make_staff, make_variant_size):
    row = make_variant_size()
    no_add = client_for(make_staff("catalog.view_variantimage", "catalog.view_colorvariant"))
    response = no_add.post(
        "/api/admin/catalog/images/upload/",
        {"variant": row.variant_id, "file": png_upload()},
    )
    assert response.status_code == 403


def test_image_reorder_sets_first_as_primary_and_rejects_partial_lists(make_staff, make_variant_size, tmp_path):
    row = make_variant_size()
    client = client_for(make_staff(
        "catalog.add_variantimage", "catalog.view_variantimage", "catalog.view_colorvariant",
        "catalog.change_variantimage",
    ))
    with override_settings(MEDIA_ROOT=tmp_path):
        first = client.post("/api/admin/catalog/images/upload/", {"variant": row.variant_id, "file": png_upload("a.png")})
        second = client.post("/api/admin/catalog/images/upload/", {"variant": row.variant_id, "file": png_upload("b.png")})
        assert first.status_code == 201 and second.status_code == 201
        ids = [first.json()["id"], second.json()["id"]]
        invalid = client.post("/api/admin/catalog/images/reorder/", {"variant": row.variant_id, "image_ids": ids[:1]}, content_type="application/json")
        assert invalid.status_code == 400
        changed = client.post("/api/admin/catalog/images/reorder/", {"variant": row.variant_id, "image_ids": list(reversed(ids))}, content_type="application/json")
        assert changed.status_code == 200, changed.content
        rows = list(VariantImage.objects.filter(variant=row.variant, is_active=True).order_by("position"))
        assert [item.pk for item in rows] == list(reversed(ids))
        assert rows[0].is_primary is True
        assert sum(item.is_primary for item in rows) == 1


def test_deactivating_primary_promotes_next_image(make_staff, make_variant_size, tmp_path):
    row = make_variant_size()
    client = client_for(make_staff(
        "catalog.add_variantimage", "catalog.view_variantimage", "catalog.view_colorvariant",
        "catalog.change_variantimage",
    ))
    with override_settings(MEDIA_ROOT=tmp_path):
        first = client.post("/api/admin/catalog/images/upload/", {"variant": row.variant_id, "file": png_upload("a.png")})
        second = client.post("/api/admin/catalog/images/upload/", {"variant": row.variant_id, "file": png_upload("b.png")})
        response = client.patch(f"/api/admin/catalog/images/{first.json()['id']}/deactivate/", {}, content_type="application/json")
        assert response.status_code == 200
        assert VariantImage.objects.get(pk=first.json()["id"]).is_active is False
        promoted = VariantImage.objects.get(pk=second.json()["id"])
        assert promoted.is_primary is True
