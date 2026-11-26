import json
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from apps.catalog.models import VariantImage
from tests.conftest import client_for

pytestmark = pytest.mark.django_db


def clear_fixture_image(row):
    # make_variant_size creates a placeholder image; these tests exercise an empty gallery.
    VariantImage.objects.filter(variant=row.variant).delete()


def png_upload(name="product.png"):
    buffer = BytesIO()
    Image.new("RGB", (32, 48), "skyblue").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def test_staff_can_upload_webp_and_first_image_becomes_primary(make_staff, make_variant_size, tmp_path):
    row = make_variant_size()
    clear_fixture_image(row)
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
    clear_fixture_image(row)
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
    clear_fixture_image(row)
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


def test_workspace_save_commits_staged_images_only_with_final_save(make_staff, make_variant_size, tmp_path):
    row = make_variant_size()
    clear_fixture_image(row)
    actor = make_staff(
        "catalog.change_product", "catalog.add_variantimage", "catalog.view_colorvariant",
    )
    client = client_for(actor)
    key = "a" * 32
    workspace = {
        "images": [{
            "variant": row.variant_id,
            "image_ids": [],
            "deactivate_ids": [],
            "new_images": [{"key": key, "alt_text": "نمای جلو"}],
            "order": [f"new:{key}"],
        }],
    }

    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            f"/api/admin/catalog/products/{row.variant.product_id}/workspace-save/",
            {"workspace": json.dumps(workspace), f"image_{key}": png_upload()},
        )
        assert response.status_code == 200, response.content
        image = VariantImage.objects.get(variant=row.variant)
        assert image.alt_text == "نمای جلو"
        assert image.is_primary is True
        assert image.position == 0
        assert (tmp_path / image.storage_key).is_file()
        assert response.json()["images"][0]["id"] == image.pk


def test_workspace_save_removes_new_files_and_rolls_back_when_later_image_fails(
    make_staff, make_variant_size, tmp_path,
):
    row = make_variant_size()
    clear_fixture_image(row)
    actor = make_staff(
        "catalog.change_product", "catalog.add_variantimage", "catalog.view_colorvariant",
        "catalog.change_variantimage",
    )
    client = client_for(actor)
    with override_settings(MEDIA_ROOT=tmp_path):
        initial = client.post(
            "/api/admin/catalog/images/upload/",
            {"variant": row.variant_id, "file": png_upload("existing.png")},
        )
        assert initial.status_code == 201, initial.content
        existing = VariantImage.objects.get(pk=initial.json()["id"])
    first_key = "b" * 32
    second_key = "c" * 32
    workspace = {
        "images": [{
            "variant": row.variant_id,
            "image_ids": [existing.pk],
            "deactivate_ids": [],
            "new_images": [
                {"key": first_key, "alt_text": "اول"},
                {"key": second_key, "alt_text": "دوم"},
            ],
            "order": [f"existing:{existing.pk}", f"new:{first_key}", f"new:{second_key}"],
        }],
    }
    invalid_upload = SimpleUploadedFile("invalid.png", b"not-an-image", content_type="image/png")

    with override_settings(MEDIA_ROOT=tmp_path):
        original_key = existing.storage_key
        response = client.post(
            f"/api/admin/catalog/products/{row.variant.product_id}/workspace-save/",
            {
                "workspace": json.dumps(workspace),
                f"image_{first_key}": png_upload("first.png"),
                f"image_{second_key}": invalid_upload,
            },
        )
        assert response.status_code == 400, response.content
        assert VariantImage.objects.filter(variant=row.variant).count() == 1
        existing.refresh_from_db()
        assert existing.storage_key == original_key
        assert existing.is_active is True
        assert (tmp_path / original_key).is_file()
        assert {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*.webp")} == {original_key}
